-- Feature 053 Integrity Remediation (T068–T075)
-- Forward fix migration adding candidate starvation filtering, full squad snapshotting,
-- durable 2-phase completion, exact 30-day rivalry window, and guild-isolated leaderboards.

-- 1) Force PvP flags to boolean false (dark state gate compliance)
INSERT INTO public.game_config (key, value_json)
VALUES
    ('battle_pvp_enabled', 'false'::jsonb),
    ('pvp_rewards_enabled', 'false'::jsonb),
    ('pvp_rivalries_enabled', 'false'::jsonb)
ON CONFLICT (key) DO UPDATE
SET value_json = EXCLUDED.value_json;

-- 2) Division rank helper
CREATE OR REPLACE FUNCTION public.pvp_division_rank(p_lp INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_rank INTEGER;
BEGIN
    SELECT rank_order INTO v_rank
    FROM (
        SELECT id, ROW_NUMBER() OVER (ORDER BY min_lp ASC) AS rank_order, min_lp
        FROM public.global_divisions
    ) d
    WHERE p_lp >= d.min_lp
    ORDER BY d.min_lp DESC
    LIMIT 1;

    RETURN COALESCE(v_rank, 1);
END;
$$;

-- 3) Search bands with max_div_diff
DROP FUNCTION IF EXISTS public._pvp_search_bands(NUMERIC);
CREATE OR REPLACE FUNCTION public._pvp_search_bands(p_wait_seconds NUMERIC)
RETURNS TABLE(max_div_diff INTEGER, max_lp INTEGER, max_ovr NUMERIC)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_wait_seconds < 15 THEN
        RETURN QUERY SELECT 0, 100, 4::NUMERIC;
    ELSIF p_wait_seconds < 30 THEN
        RETURN QUERY SELECT 1, 200, 7::NUMERIC;
    ELSIF p_wait_seconds < 60 THEN
        RETURN QUERY SELECT 2, 350, 10::NUMERIC;
    ELSE
        RETURN QUERY SELECT
            99,
            public.get_game_config_int('pvp_max_lp_range', 500)::INTEGER,
            public.get_game_config_numeric('pvp_max_ovr_range', 12);
    END IF;
END;
$$;

-- 4) Build canonical squad snapshot helper
CREATE OR REPLACE FUNCTION public.build_pvp_squad_snapshot(p_owner_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_squad JSONB;
    v_ids UUID[];
    v_meta JSONB;
    v_rating NUMERIC;
    v_policy JSONB;
BEGIN
    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player % not found', p_owner_id;
    END IF;

    SELECT
        jsonb_agg(
            jsonb_build_object(
                'name', pc.name,
                'position', sa.position,
                'overall', pc.overall,
                'pac', pc.pac,
                'sho', pc.sho,
                'pas', pc.pas,
                'dri', pc.dri,
                'def_stat', pc.def_stat,
                'phy', pc.phy,
                'morale', COALESCE(pc.morale, 80),
                'playstyles', COALESCE(pc.playstyles, '[]'::jsonb)
            ) ORDER BY sa.slot ASC
        ),
        array_agg(pc.id ORDER BY sa.slot ASC),
        jsonb_agg(
            jsonb_build_object(
                'id', pc.id,
                'level', COALESCE(pc.level, 1),
                'age', public.card_age_from_dob(pc.date_of_birth),
                'date_of_birth', pc.date_of_birth,
                'fatigue', pc.fatigue,
                'injury_tier', pc.injury_tier,
                'slot', sa.slot
            ) ORDER BY sa.slot ASC
        ),
        AVG(pc.overall)::NUMERIC
    INTO v_squad, v_ids, v_meta, v_rating
    FROM public.squad_assignments sa
    JOIN public.player_cards pc ON pc.id = sa.card_id
    WHERE sa.discord_id = p_owner_id
      AND pc.owner_id = p_owner_id
      AND COALESCE(pc.is_retired, FALSE) = FALSE;

    IF v_squad IS NULL
       OR jsonb_array_length(v_squad) <> 11
       OR cardinality(v_ids) <> 11
    THEN
        RAISE EXCEPTION 'Player % starting XI does not contain 11 valid cards', p_owner_id;
    END IF;

    v_policy := jsonb_build_object(
        'economy_enabled', COALESCE((public.get_game_config('pvp_rewards_enabled') #>> '{}')::BOOLEAN, FALSE),
        'xp_enabled', COALESCE((public.get_game_config('pvp_rewards_enabled') #>> '{}')::BOOLEAN, FALSE),
        'fitness_enabled', COALESCE((public.get_game_config('pvp_rewards_enabled') #>> '{}')::BOOLEAN, FALSE),
        'rivalry_enabled', COALESCE((public.get_game_config('pvp_rivalries_enabled') #>> '{}')::BOOLEAN, FALSE)
    );

    RETURN jsonb_build_object(
        'owner_id', p_owner_id,
        'formation', COALESCE(v_player.tactics #>> '{formation}', '4-3-3'),
        'tactics', COALESCE(v_player.tactics, '{}'::jsonb),
        'xi_rating', ROUND(v_rating, 2),
        'squad', v_squad,
        'card_ids', to_jsonb(v_ids),
        'card_meta', v_meta,
        'finalization_policy', v_policy
    );
END;
$$;

-- 5) try_match_pvp_queue with complete candidate eligibility filtering
DROP FUNCTION IF EXISTS public.try_match_pvp_queue(BIGINT);
CREATE OR REPLACE FUNCTION public.try_match_pvp_queue(
    p_guild_id BIGINT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_a public.pvp_matchmaking_queue%ROWTYPE;
    v_b public.pvp_matchmaking_queue%ROWTYPE;
    v_id1 BIGINT;
    v_id2 BIGINT;
    v_seed BIGINT;
    v_run_id UUID;
    v_token UUID := gen_random_uuid();
    v_wait NUMERIC;
    v_max_div INTEGER;
    v_max_lp INTEGER;
    v_max_ovr NUMERIC;
    v_cooldown_min INTEGER;
    v_pair_daily INTEGER;
    v_mgr_daily INTEGER;
    v_cost INTEGER;
    v_energy INTEGER;
    v_snap_a JSONB;
    v_snap_b JSONB;
    v_full_snap JSONB;
    v_a_rank INTEGER;
BEGIN
    PERFORM public.expire_pvp_queue_rows();

    IF NOT public._pvp_flag_on() THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'disabled');
    END IF;

    v_cooldown_min := public.get_game_config_int('pvp_same_pair_cooldown_minutes', 30)::INTEGER;
    v_pair_daily := public.get_game_config_int('pvp_same_pair_matches_daily', 2)::INTEGER;
    v_mgr_daily := public.get_game_config_int('pvp_rewarded_matches_daily', 5)::INTEGER;
    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;

    -- Pick oldest searching row A
    SELECT * INTO v_a
    FROM public.pvp_matchmaking_queue
    WHERE status = 'searching'
      AND expires_at >= NOW()
      AND (p_guild_id IS NULL OR guild_id = p_guild_id)
    ORDER BY joined_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'no_searchers');
    END IF;

    v_wait := EXTRACT(EPOCH FROM (NOW() - v_a.joined_at));
    SELECT max_div_diff, max_lp, max_ovr INTO v_max_div, v_max_lp, v_max_ovr
    FROM public._pvp_search_bands(v_wait);

    v_a_rank := public.pvp_division_rank(v_a.global_lp);

    -- Find eligible candidate B evaluating ALL constraints in SQL filter
    SELECT q.* INTO v_b
    FROM public.pvp_matchmaking_queue q
    WHERE q.status = 'searching'
      AND q.expires_at >= NOW()
      AND q.guild_id = v_a.guild_id
      AND q.owner_id <> v_a.owner_id
      AND q.id <> v_a.id
      AND ABS(public.pvp_division_rank(q.global_lp) - v_a_rank) <= v_max_div
      AND ABS(q.global_lp - v_a.global_lp) <= v_max_lp
      AND ABS(q.xi_rating - v_a.xi_rating) <= v_max_ovr
      -- Blocks check
      AND NOT EXISTS (
          SELECT 1 FROM public.pvp_blocks blk
          WHERE (blk.blocker_id = v_a.owner_id AND blk.blocked_id = q.owner_id)
             OR (blk.blocker_id = q.owner_id AND blk.blocked_id = v_a.owner_id)
      )
      -- Match locks check
      AND NOT EXISTS (
          SELECT 1 FROM public.match_locks ml
          WHERE ml.discord_id IN (v_a.owner_id, q.owner_id)
      )
      -- Same-pair cooldown check
      AND NOT EXISTS (
          SELECT 1 FROM public.match_history mh
          WHERE mh.match_type = 'pvp'
            AND mh.player_id = v_a.owner_id
            AND mh.opponent_owner_id = q.owner_id
            AND mh.played_at > NOW() - make_interval(mins => v_cooldown_min)
      )
      -- Same-pair daily cap check
      AND (
          SELECT COUNT(*) FROM public.match_history mh
          WHERE mh.match_type = 'pvp'
            AND mh.player_id = v_a.owner_id
            AND mh.opponent_owner_id = q.owner_id
            AND (mh.played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE
      ) < v_pair_daily
      -- Manager daily cap check for searcher A
      AND (
          SELECT COUNT(*) FROM public.match_history mh
          WHERE mh.player_id = v_a.owner_id
            AND mh.match_type = 'pvp'
            AND (mh.played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE
      ) < v_mgr_daily
      -- Manager daily cap check for candidate B
      AND (
          SELECT COUNT(*) FROM public.match_history mh
          WHERE mh.player_id = q.owner_id
            AND mh.match_type = 'pvp'
            AND (mh.played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE
      ) < v_mgr_daily
    ORDER BY
        ABS(public.pvp_division_rank(q.global_lp) - v_a_rank) ASC,
        ABS(q.global_lp - v_a.global_lp) ASC,
        ABS(q.xi_rating - v_a.xi_rating) ASC,
        q.joined_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'no_partner', 'queue_id', v_a.id);
    END IF;

    -- Energy + XI revalidation
    PERFORM public.sync_action_energy(v_a.owner_id);
    PERFORM public.sync_action_energy(v_b.owner_id);
    SELECT action_energy INTO v_energy FROM public.players WHERE discord_id = v_a.owner_id;
    IF COALESCE(v_energy, 0) < v_cost THEN
        UPDATE public.pvp_matchmaking_queue
        SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
        WHERE id = v_a.id;
        RETURN jsonb_build_object('matched', false, 'reason', 'energy_a');
    END IF;

    SELECT action_energy INTO v_energy FROM public.players WHERE discord_id = v_b.owner_id;
    IF COALESCE(v_energy, 0) < v_cost THEN
        UPDATE public.pvp_matchmaking_queue
        SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
        WHERE id = v_b.id;
        RETURN jsonb_build_object('matched', false, 'reason', 'energy_b');
    END IF;

    BEGIN
        v_snap_a := public.build_pvp_squad_snapshot(v_a.owner_id);
        v_snap_b := public.build_pvp_squad_snapshot(v_b.owner_id);
    EXCEPTION WHEN OTHERS THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'xi_invalid');
    END;

    UPDATE public.pvp_matchmaking_queue
    SET status = 'matching', claim_token = v_token, updated_at = NOW()
    WHERE id IN (v_a.id, v_b.id);

    IF v_a.owner_id < v_b.owner_id THEN
        v_id1 := v_a.owner_id; v_id2 := v_b.owner_id;
    ELSE
        v_id1 := v_b.owner_id; v_id2 := v_a.owner_id;
    END IF;

    IF NOT public.acquire_match_lock(v_id1, 'pvp') THEN
        UPDATE public.pvp_matchmaking_queue
        SET status = 'searching', claim_token = NULL, updated_at = NOW()
        WHERE id IN (v_a.id, v_b.id);
        RETURN jsonb_build_object('matched', false, 'reason', 'lock_failed');
    END IF;
    IF NOT public.acquire_match_lock(v_id2, 'pvp') THEN
        PERFORM public.release_match_lock(v_id1);
        UPDATE public.pvp_matchmaking_queue
        SET status = 'searching', claim_token = NULL, updated_at = NOW()
        WHERE id IN (v_a.id, v_b.id);
        RETURN jsonb_build_object('matched', false, 'reason', 'lock_failed');
    END IF;

    v_seed := (floor(random() * 9223372036854775807))::BIGINT;
    v_full_snap := jsonb_build_object(
        'home_owner_id', v_a.owner_id,
        'away_owner_id', v_b.owner_id,
        'home_xi_rating', v_a.xi_rating,
        'away_xi_rating', v_b.xi_rating,
        'home_lp', v_a.global_lp,
        'away_lp', v_b.global_lp,
        'home_formation', v_snap_a #>> '{formation}',
        'away_formation', v_snap_b #>> '{formation}',
        'home_tactics', v_snap_a -> 'tactics',
        'away_tactics', v_snap_b -> 'tactics',
        'home_squad', v_snap_a -> 'squad',
        'away_squad', v_snap_b -> 'squad',
        'home_card_ids', v_snap_a -> 'card_ids',
        'away_card_ids', v_snap_b -> 'card_ids',
        'home_card_meta', v_snap_a -> 'card_meta',
        'away_card_meta', v_snap_b -> 'card_meta',
        'finalization_policy', v_snap_a -> 'finalization_policy'
    );

    INSERT INTO public.match_runs (
        run_type, status, home_discord_id, away_discord_id, active_discord_id,
        sim_seed, squad_snapshot, guild_id, channel_id
    ) VALUES (
        'pvp', 'streaming', v_a.owner_id, v_b.owner_id, v_a.owner_id,
        v_seed, v_full_snap, v_a.guild_id, v_a.channel_id
    ) RETURNING id INTO v_run_id;

    UPDATE public.pvp_matchmaking_queue
    SET status = 'matched', matched_run_id = v_run_id, updated_at = NOW()
    WHERE id IN (v_a.id, v_b.id);

    RETURN jsonb_build_object(
        'matched', true,
        'run_id', v_run_id,
        'home_owner_id', v_a.owner_id,
        'away_owner_id', v_b.owner_id,
        'guild_id', v_a.guild_id,
        'channel_id', v_a.channel_id,
        'sim_seed', v_seed,
        'squad_snapshot', v_full_snap
    );
END;
$$;

-- 6) Preflight cleanup & Unique index on match_history(run_id, player_id)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.match_history
        WHERE run_id IS NOT NULL
        GROUP BY run_id, player_id HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Unexpected duplicate match_history rows detected prior to unique index creation.';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_match_history_run_player
ON public.match_history (run_id, player_id)
WHERE run_id IS NOT NULL;

-- 7) Replace _upsert_rivalry_from_pvp with exact 30-day window count & correct PK update
DROP FUNCTION IF EXISTS public._upsert_rivalry_from_pvp(BIGINT, BIGINT, INTEGER, INTEGER);
CREATE OR REPLACE FUNCTION public._upsert_rivalry_from_pvp(
    p_home_id BIGINT,
    p_away_id BIGINT,
    p_home_score INTEGER,
    p_away_score INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_a BIGINT := LEAST(p_home_id, p_away_id);
    v_b BIGINT := GREATEST(p_home_id, p_away_id);
    v_winner BIGINT;
    v_act_matches INTEGER;
    v_act_days INTEGER;
    v_row public.manager_rivalries%ROWTYPE;
    v_rivalry_exists BOOLEAN;
    v_meetings INTEGER;
    v_meetings_30d INTEGER;
    v_a_wins INTEGER;
    v_b_wins INTEGER;
    v_draws INTEGER;
    v_a_goals INTEGER;
    v_b_goals INTEGER;
    v_streak_owner BIGINT;
    v_streak_count INTEGER;
    v_status TEXT;
    v_activated TIMESTAMPTZ;
    v_events JSONB := '[]'::jsonb;
BEGIN
    IF p_home_score > p_away_score THEN v_winner := p_home_id;
    ELSIF p_home_score < p_away_score THEN v_winner := p_away_id;
    ELSE v_winner := NULL;
    END IF;

    v_act_matches := public.get_game_config_int('pvp_rivalry_activation_matches', 3)::INTEGER;
    v_act_days := public.get_game_config_int('pvp_rivalry_activation_days', 30)::INTEGER;

    SELECT * INTO v_row FROM public.manager_rivalries
    WHERE manager_a_id = v_a AND manager_b_id = v_b FOR UPDATE;

    v_rivalry_exists := FOUND;

    SELECT COUNT(*) INTO v_meetings_30d
    FROM public.match_history
    WHERE player_id = v_a
      AND opponent_owner_id = v_b
      AND match_type = 'pvp'
      AND played_at >= NOW() - make_interval(days => v_act_days);

    IF NOT v_rivalry_exists THEN
        v_meetings := 1;
        v_a_wins := CASE WHEN v_winner = v_a THEN 1 ELSE 0 END;
        v_b_wins := CASE WHEN v_winner = v_b THEN 1 ELSE 0 END;
        v_draws := CASE WHEN v_winner IS NULL THEN 1 ELSE 0 END;
        IF p_home_id = v_a THEN v_a_goals := p_home_score; v_b_goals := p_away_score;
        ELSE v_a_goals := p_away_score; v_b_goals := p_home_score; END IF;
        v_streak_owner := v_winner;
        v_streak_count := CASE WHEN v_winner IS NULL THEN 0 ELSE 1 END;
        v_status := CASE WHEN v_meetings_30d >= v_act_matches THEN 'active' ELSE 'tracking' END;
        v_activated := CASE WHEN v_status = 'active' THEN NOW() ELSE NULL END;
        INSERT INTO public.manager_rivalries (
            manager_a_id, manager_b_id, meetings, a_wins, b_wins, draws,
            a_goals, b_goals, current_streak_owner, current_streak_count,
            longest_streak_owner, longest_streak_count, last_winner_id,
            last_result, last_match_at, first_meeting_in_window_at, status, activated_at
        ) VALUES (
            v_a, v_b, v_meetings, v_a_wins, v_b_wins, v_draws,
            v_a_goals, v_b_goals, v_streak_owner, v_streak_count,
            v_streak_owner, v_streak_count, v_winner,
            CASE WHEN v_winner IS NULL THEN 'draw' WHEN v_winner = v_a THEN 'a_win' ELSE 'b_win' END,
            NOW(), NOW(), v_status, v_activated
        );
    ELSE
        v_meetings := v_row.meetings + 1;
        v_a_wins := v_row.a_wins + CASE WHEN v_winner = v_a THEN 1 ELSE 0 END;
        v_b_wins := v_row.b_wins + CASE WHEN v_winner = v_b THEN 1 ELSE 0 END;
        v_draws := v_row.draws + CASE WHEN v_winner IS NULL THEN 1 ELSE 0 END;
        IF p_home_id = v_a THEN v_a_goals := v_row.a_goals + p_home_score; v_b_goals := v_row.b_goals + p_away_score;
        ELSE v_a_goals := v_row.a_goals + p_away_score; v_b_goals := v_row.b_goals + p_home_score; END IF;

        IF v_winner IS NULL THEN v_streak_owner := NULL; v_streak_count := 0;
        ELSIF v_winner = v_row.current_streak_owner THEN v_streak_owner := v_winner; v_streak_count := v_row.current_streak_count + 1;
        ELSE
            IF v_row.current_streak_owner IS NOT NULL AND v_row.current_streak_count >= 3 THEN
                v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'streak_broken'), jsonb_build_object('code', 'revenge_served'));
            END IF;
            v_streak_owner := v_winner; v_streak_count := 1;
        END IF;

        v_status := v_row.status; v_activated := v_row.activated_at;
        IF v_status = 'dormant' THEN v_status := 'tracking'; END IF;
        IF v_status IN ('tracking', 'dormant') AND v_meetings_30d >= v_act_matches THEN
            v_status := 'active'; v_activated := NOW();
            v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'rivalry_activated', 'message', 'Third ranked meeting in 30 days — rivalry activated.'));
        END IF;

        UPDATE public.manager_rivalries SET
            meetings = v_meetings, a_wins = v_a_wins, b_wins = v_b_wins, draws = v_draws,
            a_goals = v_a_goals, b_goals = v_b_goals, current_streak_owner = v_streak_owner,
            current_streak_count = v_streak_count,
            longest_streak_owner = CASE WHEN v_streak_count > COALESCE(v_row.longest_streak_count,0) THEN v_streak_owner ELSE v_row.longest_streak_owner END,
            longest_streak_count = GREATEST(COALESCE(v_row.longest_streak_count,0), v_streak_count),
            last_winner_id = v_winner,
            last_result = CASE WHEN v_winner IS NULL THEN 'draw' WHEN v_winner = v_a THEN 'a_win' ELSE 'b_win' END,
            last_match_at = NOW(), status = v_status, activated_at = v_activated, updated_at = NOW()
        WHERE manager_a_id = v_a AND manager_b_id = v_b;
    END IF;

    RETURN jsonb_build_object('status', v_status, 'events', v_events);
END;
$$;

-- 8) Replace finalize_pvp_match (Phase 1 idempotency + snapshotted policy)
DROP FUNCTION IF EXISTS public.finalize_pvp_match(UUID, INTEGER, INTEGER, NUMERIC, NUMERIC);
CREATE OR REPLACE FUNCTION public.finalize_pvp_match(
    p_run_id UUID,
    p_home_score INTEGER,
    p_away_score INTEGER,
    p_home_rating NUMERIC,
    p_away_rating NUMERIC
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_home public.players%ROWTYPE;
    v_away public.players%ROWTYPE;
    v_home_res TEXT;
    v_away_res TEXT;
    v_home_coins INTEGER := 0;
    v_away_coins INTEGER := 0;
    v_home_lp INTEGER := 0;
    v_away_lp INTEGER := 0;
    v_hist_home UUID;
    v_hist_away UUID;
    v_policy JSONB;
    v_rewards BOOLEAN;
    v_rivalries BOOLEAN;
    v_cost INTEGER;
    v_prov INTEGER;
    v_raw_lp INTEGER;
    v_new_lp INTEGER;
    v_mult_win NUMERIC;
    v_mult_draw NUMERIC;
    v_mult_loss NUMERIC;
    v_rivalry JSONB := '{}'::jsonb;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Match run % not found', p_run_id;
    END IF;

    IF v_run.status IN ('completing', 'completed') THEN
        SELECT id INTO v_hist_home FROM public.match_history WHERE run_id = p_run_id AND player_id = v_run.home_discord_id;
        SELECT id INTO v_hist_away FROM public.match_history WHERE run_id = p_run_id AND player_id = v_run.away_discord_id;
        RETURN jsonb_build_object(
            'ok', true,
            'run_id', p_run_id,
            'idempotent_replay', true,
            'status', v_run.status,
            'home', jsonb_build_object('owner_id', v_run.home_discord_id, 'history_id', v_hist_home, 'rating', p_home_rating),
            'away', jsonb_build_object('owner_id', v_run.away_discord_id, 'history_id', v_hist_away, 'rating', p_away_rating)
        );
    END IF;

    SELECT * INTO v_home FROM public.players WHERE discord_id = v_run.home_discord_id FOR UPDATE;
    SELECT * INTO v_away FROM public.players WHERE discord_id = v_run.away_discord_id FOR UPDATE;

    v_policy := COALESCE(v_run.squad_snapshot -> 'finalization_policy', '{}'::jsonb);
    v_rewards := COALESCE((v_policy #>> '{economy_enabled}')::BOOLEAN, FALSE);
    v_rivalries := COALESCE((v_policy #>> '{rivalry_enabled}')::BOOLEAN, FALSE);

    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;
    v_prov := public.get_game_config_int('pvp_provisional_matches', 5)::INTEGER;

    v_home_res := CASE WHEN p_home_score > p_away_score THEN 'win' WHEN p_home_score < p_away_score THEN 'loss' ELSE 'draw' END;
    v_away_res := CASE WHEN p_away_score > p_home_score THEN 'win' WHEN p_away_score < p_home_score THEN 'loss' ELSE 'draw' END;

    IF v_rewards THEN
        PERFORM public.apply_club_economy(v_home.discord_id, 0, -v_cost, 'pvp_energy', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));
        PERFORM public.apply_club_economy(v_away.discord_id, 0, -v_cost, 'pvp_energy', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));

        v_mult_win := public.get_game_config_numeric('pvp_coin_multiplier_win', 1.25);
        v_mult_draw := public.get_game_config_numeric('pvp_coin_multiplier_draw', 1.10);
        v_mult_loss := public.get_game_config_numeric('pvp_coin_multiplier_loss', 1.00);

        v_home_coins := ROUND(100 * CASE v_home_res WHEN 'win' THEN v_mult_win WHEN 'draw' THEN v_mult_draw ELSE v_mult_loss END)::INTEGER;
        v_away_coins := ROUND(100 * CASE v_away_res WHEN 'win' THEN v_mult_win WHEN 'draw' THEN v_mult_draw ELSE v_mult_loss END)::INTEGER;

        PERFORM public.apply_club_economy(v_home.discord_id, v_home_coins, 0, 'pvp_reward', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));
        PERFORM public.apply_club_economy(v_away.discord_id, v_away_coins, 0, 'pvp_reward', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));

        v_raw_lp := CASE v_home_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_home_res = 'loss' AND COALESCE(v_home.pvp_ranked_matches, 0) < v_prov THEN v_raw_lp := v_raw_lp / 2; END IF;
        v_new_lp := GREATEST(0, v_home.global_lp + v_raw_lp);
        v_home_lp := v_new_lp - v_home.global_lp;

        v_raw_lp := CASE v_away_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_away_res = 'loss' AND COALESCE(v_away.pvp_ranked_matches, 0) < v_prov THEN v_raw_lp := v_raw_lp / 2; END IF;
        v_new_lp := GREATEST(0, v_away.global_lp + v_raw_lp);
        v_away_lp := v_new_lp - v_away.global_lp;

        PERFORM public.increment_match_career_stats(v_home.discord_id, v_home_res, CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END, v_home_lp, p_home_score - p_away_score);
        PERFORM public.increment_match_career_stats(v_away.discord_id, v_away_res, CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END, v_away_lp, p_away_score - p_home_score);
        UPDATE public.players SET pvp_ranked_matches = COALESCE(pvp_ranked_matches, 0) + 1 WHERE discord_id IN (v_home.discord_id, v_away.discord_id);
    END IF;

    -- Conflict-safe insert match history rows
    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        v_home.discord_id, v_home_res, p_home_rating, p_away_rating,
        p_home_score, p_away_score, v_home_coins,
        CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_away.discord_id, 'pvp', v_home_lp, v_rivalries
    ) ON CONFLICT (run_id, player_id) WHERE run_id IS NOT NULL DO UPDATE SET run_id = EXCLUDED.run_id
    RETURNING id INTO v_hist_home;

    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        v_away.discord_id, v_away_res, p_away_rating, p_home_rating,
        p_away_score, p_home_score, v_away_coins,
        CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_home.discord_id, 'pvp', v_away_lp, v_rivalries
    ) ON CONFLICT (run_id, player_id) WHERE run_id IS NOT NULL DO UPDATE SET run_id = EXCLUDED.run_id
    RETURNING id INTO v_hist_away;

    IF v_rivalries THEN
        v_rivalry := public._upsert_rivalry_from_pvp(v_home.discord_id, v_away.discord_id, p_home_score, p_away_score);
    END IF;

    -- Mark status completing (holds locks until complete_pvp_run)
    UPDATE public.match_runs SET
        status = 'completing', home_score = p_home_score, away_score = p_away_score,
        last_minute = 90, completion_key = p_run_id::TEXT, updated_at = NOW()
    WHERE id = p_run_id;

    RETURN jsonb_build_object(
        'ok', true,
        'run_id', p_run_id,
        'rewards_skipped', NOT v_rewards,
        'rivalry', v_rivalry,
        'home', jsonb_build_object('owner_id', v_home.discord_id, 'result', v_home_res, 'coins', v_home_coins, 'lp_delta', v_home_lp, 'history_id', v_hist_home, 'rating', p_home_rating),
        'away', jsonb_build_object('owner_id', v_away.discord_id, 'result', v_away_res, 'coins', v_away_coins, 'lp_delta', v_away_lp, 'history_id', v_hist_away, 'rating', p_away_rating)
    );
END;
$$;

-- 9) Atomic exactly-once XP RPC with strict relational validation
CREATE OR REPLACE FUNCTION public.apply_pvp_match_xp_once(
    p_history_id UUID,
    p_run_id UUID,
    p_owner_id BIGINT,
    p_result_str TEXT,
    p_cards JSONB,
    p_team_rating NUMERIC
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_hist public.match_history%ROWTYPE;
    v_card JSONB;
    v_card_id UUID;
    v_card_owner BIGINT;
    v_xp INTEGER;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id;
    IF NOT FOUND OR v_run.run_type <> 'pvp' OR v_run.status <> 'completing' THEN
        RAISE EXCEPTION 'Invalid match run % for XP application', p_run_id;
    END IF;

    SELECT * INTO v_hist FROM public.match_history WHERE id = p_history_id FOR UPDATE;
    IF NOT FOUND OR v_hist.run_id <> p_run_id OR v_hist.player_id <> p_owner_id OR v_hist.match_type <> 'pvp' THEN
        RAISE EXCEPTION 'Match history % does not match run % and player %', p_history_id, p_run_id, p_owner_id;
    END IF;

    IF v_hist.xp_applied_at IS NOT NULL THEN
        RETURN jsonb_build_object('ok', true, 'already_applied', true);
    END IF;

    FOR v_card IN SELECT * FROM jsonb_array_elements(p_cards) LOOP
        v_card_id := (v_card #>> '{id}')::UUID;
        IF v_card_id IS NOT NULL THEN
            SELECT owner_id INTO v_card_owner FROM public.player_cards WHERE id = v_card_id;
            IF v_card_owner = p_owner_id THEN
                v_xp := public.match_xp_reward(p_result_str, (v_card #>> '{level}')::INTEGER, (v_card #>> '{date_of_birth}')::DATE, 'pvp');
                IF v_xp > 0 THEN
                    PERFORM public.apply_card_xp(v_card_id, v_xp, 'pvp_match');
                END IF;
            END IF;
        END IF;
    END LOOP;

    UPDATE public.match_history SET xp_applied_at = NOW() WHERE id = p_history_id;
    RETURN jsonb_build_object('ok', true, 'applied', true);
END;
$$;

-- 10) Atomic exactly-once Fitness RPC with injury persistence
CREATE OR REPLACE FUNCTION public.apply_pvp_post_match_fitness_once(
    p_history_id UUID,
    p_run_id UUID,
    p_owner_id BIGINT,
    p_starter_drains JSONB,
    p_bench_ids UUID[],
    p_recorded_injuries JSONB DEFAULT '[]'::jsonb
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_hist public.match_history%ROWTYPE;
    v_drain JSONB;
    v_inj JSONB;
    v_card_id UUID;
    v_amt INTEGER;
    v_tier TEXT;
    v_days INTEGER;
    v_until TIMESTAMPTZ;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id;
    IF NOT FOUND OR v_run.run_type <> 'pvp' OR v_run.status <> 'completing' THEN
        RAISE EXCEPTION 'Invalid match run % for fitness application', p_run_id;
    END IF;

    SELECT * INTO v_hist FROM public.match_history WHERE id = p_history_id FOR UPDATE;
    IF NOT FOUND OR v_hist.run_id <> p_run_id OR v_hist.player_id <> p_owner_id OR v_hist.match_type <> 'pvp' THEN
        RAISE EXCEPTION 'Match history % does not match run % and player %', p_history_id, p_run_id, p_owner_id;
    END IF;

    IF v_hist.fatigue_applied_at IS NOT NULL THEN
        RETURN jsonb_build_object('ok', true, 'already_applied', true);
    END IF;

    -- Apply starter drains
    FOR v_drain IN SELECT * FROM jsonb_array_elements(p_starter_drains) LOOP
        v_card_id := (v_drain #>> '{id}')::UUID;
        v_amt := (v_drain #>> '{drain}')::INTEGER;
        IF v_card_id IS NOT NULL AND v_amt > 0 THEN
            UPDATE public.player_cards
            SET fatigue = GREATEST(0, fatigue - v_amt)
            WHERE id = v_card_id AND owner_id = p_owner_id;
        END IF;
    END LOOP;

    -- Bench recovery (+25 fatigue)
    IF array_length(p_bench_ids, 1) > 0 THEN
        UPDATE public.player_cards
        SET fatigue = LEAST(100, fatigue + 25)
        WHERE id = ANY(p_bench_ids) AND owner_id = p_owner_id;
    END IF;

    -- Process recorded injuries
    FOR v_inj IN SELECT * FROM jsonb_array_elements(p_recorded_injuries) LOOP
        v_card_id := COALESCE((v_inj #>> '{id}')::UUID, (v_inj #>> '{player_card_id}')::UUID);
        v_tier := v_inj #>> '{tier}';
        v_days := COALESCE((v_inj #>> '{days}')::INTEGER, (v_inj #>> '{recovery_days}')::INTEGER, 2);
        IF v_card_id IS NOT NULL AND v_tier IS NOT NULL THEN
            IF v_tier ~ '^[0-9]+$' THEN
                v_tier := CASE v_tier::INTEGER WHEN 1 THEN 'minor' WHEN 2 THEN 'moderate' WHEN 3 THEN 'major' ELSE 'minor' END;
            END IF;
            v_until := NOW() + make_interval(days => GREATEST(1, v_days));
            UPDATE public.player_cards
            SET injury_tier = v_tier, hospitalized_until = v_until
            WHERE id = v_card_id AND owner_id = p_owner_id;
        END IF;
    END LOOP;

    UPDATE public.match_history SET fatigue_applied_at = NOW() WHERE id = p_history_id;
    RETURN jsonb_build_object('ok', true, 'applied', true);
END;
$$;

-- 11) Server-validated completion RPC
CREATE OR REPLACE FUNCTION public.complete_pvp_run(
    p_run_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_policy JSONB;
    v_xp_req BOOLEAN;
    v_fit_req BOOLEAN;
    v_home_hist public.match_history%ROWTYPE;
    v_away_hist public.match_history%ROWTYPE;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND OR v_run.run_type <> 'pvp' OR v_run.status <> 'completing' THEN
        RAISE EXCEPTION 'Invalid match run % for completion', p_run_id;
    END IF;

    v_policy := COALESCE(v_run.squad_snapshot -> 'finalization_policy', '{}'::jsonb);
    v_xp_req := COALESCE((v_policy #>> '{xp_enabled}')::BOOLEAN, FALSE);
    v_fit_req := COALESCE((v_policy #>> '{fitness_enabled}')::BOOLEAN, FALSE);

    SELECT * INTO v_home_hist FROM public.match_history WHERE run_id = p_run_id AND player_id = v_run.home_discord_id AND match_type = 'pvp';
    SELECT * INTO v_away_hist FROM public.match_history WHERE run_id = p_run_id AND player_id = v_run.away_discord_id AND match_type = 'pvp';

    IF v_home_hist.id IS NULL OR v_away_hist.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'missing_history_rows');
    END IF;

    IF v_xp_req AND (v_home_hist.xp_applied_at IS NULL OR v_away_hist.xp_applied_at IS NULL) THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'missing_xp_stamps');
    END IF;

    IF v_fit_req AND (v_home_hist.fatigue_applied_at IS NULL OR v_away_hist.fatigue_applied_at IS NULL) THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'missing_fatigue_stamps');
    END IF;

    UPDATE public.match_runs
    SET status = 'completed', completed_at = NOW(), updated_at = NOW()
    WHERE id = p_run_id;

    PERFORM public.release_match_lock(v_run.home_discord_id);
    PERFORM public.release_match_lock(v_run.away_discord_id);

    RETURN jsonb_build_object('ok', true, 'completed', true);
END;
$$;

-- 12) Replace get_server_hottest_rivalries with guild isolation + one-row-per-run filtering
DROP FUNCTION IF EXISTS public.get_server_hottest_rivalries(BIGINT, INTEGER);
CREATE OR REPLACE FUNCTION public.get_server_hottest_rivalries(
    p_guild_id BIGINT,
    p_limit INTEGER DEFAULT 10
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_out JSONB;
BEGIN
    SELECT COALESCE(jsonb_agg(row_to_json(t)::JSONB), '[]'::JSONB)
    INTO v_out
    FROM (
        SELECT
            LEAST(mh.player_id, mh.opponent_owner_id) AS manager_a_id,
            GREATEST(mh.player_id, mh.opponent_owner_id) AS manager_b_id,
            COUNT(*)::INTEGER AS meetings,
            COUNT(*) FILTER (WHERE (mh.player_id < mh.opponent_owner_id AND mh.result = 'win') OR (mh.player_id > mh.opponent_owner_id AND mh.result = 'loss'))::INTEGER AS a_wins,
            COUNT(*) FILTER (WHERE (mh.player_id > mh.opponent_owner_id AND mh.result = 'win') OR (mh.player_id < mh.opponent_owner_id AND mh.result = 'loss'))::INTEGER AS b_wins,
            COUNT(*) FILTER (WHERE mh.result = 'draw')::INTEGER AS draws,
            MAX(mh.played_at) AS last_match_at,
            COUNT(*) FILTER (WHERE mh.played_at > NOW() - INTERVAL '30 days')::INTEGER AS meetings_30d
        FROM public.match_history mh
        JOIN public.match_runs mr ON mr.id = mh.run_id
        WHERE mh.match_type = 'pvp'
          AND mr.guild_id = p_guild_id
          AND mh.player_id = LEAST(mh.player_id, mh.opponent_owner_id)
        GROUP BY LEAST(mh.player_id, mh.opponent_owner_id), GREATEST(mh.player_id, mh.opponent_owner_id)
        ORDER BY meetings_30d DESC, ABS(
            COUNT(*) FILTER (WHERE (mh.player_id < mh.opponent_owner_id AND mh.result = 'win') OR (mh.player_id > mh.opponent_owner_id AND mh.result = 'loss')) -
            COUNT(*) FILTER (WHERE (mh.player_id > mh.opponent_owner_id AND mh.result = 'win') OR (mh.player_id < mh.opponent_owner_id AND mh.result = 'loss'))
        ) ASC, MAX(mh.played_at) DESC
        LIMIT GREATEST(1, LEAST(p_limit, 25))
    ) t;

    RETURN jsonb_build_object('guild_id', p_guild_id, 'rivalries', v_out);
END;
$$;

-- Security & permissions: Restrict progression RPCs to service_role ONLY
REVOKE ALL ON FUNCTION public.apply_pvp_match_xp_once(UUID, UUID, BIGINT, TEXT, JSONB, NUMERIC) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_pvp_match_xp_once(UUID, UUID, BIGINT, TEXT, JSONB, NUMERIC) TO service_role;

REVOKE ALL ON FUNCTION public.apply_pvp_post_match_fitness_once(UUID, UUID, BIGINT, JSONB, UUID[], JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_pvp_post_match_fitness_once(UUID, UUID, BIGINT, JSONB, UUID[], JSONB) TO service_role;

REVOKE ALL ON FUNCTION public.complete_pvp_run(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_pvp_run(UUID) TO service_role;

GRANT EXECUTE ON FUNCTION public.pvp_division_rank(INTEGER) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.build_pvp_squad_snapshot(BIGINT) TO anon, authenticated, service_role;

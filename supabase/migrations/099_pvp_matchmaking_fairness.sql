-- Feature 053 US4: harden try_match_pvp_queue fairness + battle hub state RPC
-- Forward fix after 098 (do not edit 098 in place).

CREATE OR REPLACE FUNCTION public._pvp_search_bands(p_wait_seconds NUMERIC)
RETURNS TABLE(max_lp INTEGER, max_ovr NUMERIC)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_wait_seconds < 15 THEN
        RETURN QUERY SELECT 100, 4::NUMERIC;
    ELSIF p_wait_seconds < 30 THEN
        RETURN QUERY SELECT 200, 7::NUMERIC;
    ELSIF p_wait_seconds < 60 THEN
        RETURN QUERY SELECT 350, 10::NUMERIC;
    ELSE
        RETURN QUERY SELECT
            public.get_game_config_int('pvp_max_lp_range', 500)::INTEGER,
            public.get_game_config_numeric('pvp_max_ovr_range', 12);
    END IF;
END;
$$;

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
    v_max_lp INTEGER;
    v_max_ovr NUMERIC;
    v_cooldown_min INTEGER;
    v_pair_daily INTEGER;
    v_mgr_daily INTEGER;
    v_cost INTEGER;
    v_energy INTEGER;
    v_xi INTEGER;
    v_pair_count INTEGER;
    v_a_day INTEGER;
    v_b_day INTEGER;
    v_last TIMESTAMPTZ;
BEGIN
    PERFORM public.expire_pvp_queue_rows();

    IF NOT public._pvp_flag_on() THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'disabled');
    END IF;

    v_cooldown_min := public.get_game_config_int('pvp_same_pair_cooldown_minutes', 30)::INTEGER;
    v_pair_daily := public.get_game_config_int('pvp_same_pair_matches_daily', 2)::INTEGER;
    v_mgr_daily := public.get_game_config_int('pvp_rewarded_matches_daily', 5)::INTEGER;
    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;

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
    SELECT max_lp, max_ovr INTO v_max_lp, v_max_ovr
    FROM public._pvp_search_bands(v_wait);

    SELECT * INTO v_b
    FROM public.pvp_matchmaking_queue q
    WHERE q.status = 'searching'
      AND q.expires_at >= NOW()
      AND q.guild_id = v_a.guild_id
      AND q.owner_id <> v_a.owner_id
      AND q.id <> v_a.id
      AND ABS(q.global_lp - v_a.global_lp) <= v_max_lp
      AND ABS(q.xi_rating - v_a.xi_rating) <= v_max_ovr
      AND NOT EXISTS (
          SELECT 1 FROM public.pvp_blocks blk
          WHERE (blk.blocker_id = v_a.owner_id AND blk.blocked_id = q.owner_id)
             OR (blk.blocker_id = q.owner_id AND blk.blocked_id = v_a.owner_id)
      )
      AND NOT EXISTS (
          SELECT 1 FROM public.match_locks ml
          WHERE ml.discord_id IN (v_a.owner_id, q.owner_id)
      )
    ORDER BY
        ABS(q.global_lp - v_a.global_lp) ASC,
        ABS(q.xi_rating - v_a.xi_rating) ASC,
        q.joined_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'no_partner', 'queue_id', v_a.id);
    END IF;

    -- Same-pair cooldown + daily pair cap
    SELECT MAX(mh.played_at), COUNT(*) FILTER (
        WHERE (mh.played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE
    )::INTEGER
    INTO v_last, v_pair_count
    FROM public.match_history mh
    WHERE mh.match_type = 'pvp'
      AND mh.player_id = v_a.owner_id
      AND mh.opponent_owner_id = v_b.owner_id;

    IF v_last IS NOT NULL AND v_last > NOW() - make_interval(mins => v_cooldown_min) THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'pair_cooldown');
    END IF;
    IF COALESCE(v_pair_count, 0) >= v_pair_daily THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'pair_daily_cap');
    END IF;

    SELECT COUNT(*)::INTEGER INTO v_a_day
    FROM public.match_history
    WHERE player_id = v_a.owner_id AND match_type = 'pvp'
      AND (played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;
    SELECT COUNT(*)::INTEGER INTO v_b_day
    FROM public.match_history
    WHERE player_id = v_b.owner_id AND match_type = 'pvp'
      AND (played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;
    IF v_a_day >= v_mgr_daily OR v_b_day >= v_mgr_daily THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'manager_daily_cap');
    END IF;

    -- Authoritative revalidate energy + XI
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

    SELECT COUNT(*)::INTEGER INTO v_xi FROM public.squad_assignments WHERE discord_id = v_a.owner_id;
    IF v_xi <> 11 THEN
        UPDATE public.pvp_matchmaking_queue
        SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
        WHERE id = v_a.id;
        RETURN jsonb_build_object('matched', false, 'reason', 'xi_a');
    END IF;
    SELECT COUNT(*)::INTEGER INTO v_xi FROM public.squad_assignments WHERE discord_id = v_b.owner_id;
    IF v_xi <> 11 THEN
        UPDATE public.pvp_matchmaking_queue
        SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
        WHERE id = v_b.id;
        RETURN jsonb_build_object('matched', false, 'reason', 'xi_b');
    END IF;

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

    INSERT INTO public.match_runs (
        run_type, status, home_discord_id, away_discord_id, active_discord_id,
        sim_seed, squad_snapshot, guild_id, channel_id
    ) VALUES (
        'pvp', 'streaming', v_a.owner_id, v_b.owner_id, v_a.owner_id,
        v_seed,
        jsonb_build_object(
            'home_owner_id', v_a.owner_id,
            'away_owner_id', v_b.owner_id,
            'home_xi_rating', v_a.xi_rating,
            'away_xi_rating', v_b.xi_rating,
            'home_lp', v_a.global_lp,
            'away_lp', v_b.global_lp
        ),
        v_a.guild_id,
        v_a.channel_id
    )
    RETURNING id INTO v_run_id;

    UPDATE public.pvp_matchmaking_queue
    SET status = 'matched', matched_run_id = v_run_id, updated_at = NOW()
    WHERE id IN (v_a.id, v_b.id);

    RETURN jsonb_build_object(
        'matched', true,
        'run_id', v_run_id,
        'sim_seed', v_seed,
        'home_owner_id', v_a.owner_id,
        'away_owner_id', v_b.owner_id,
        'guild_id', v_a.guild_id,
        'channel_id', v_a.channel_id,
        'queue_ids', jsonb_build_array(v_a.id, v_b.id)
    );
EXCEPTION WHEN OTHERS THEN
    IF v_id1 IS NOT NULL THEN PERFORM public.release_match_lock(v_id1); END IF;
    IF v_id2 IS NOT NULL THEN PERFORM public.release_match_lock(v_id2); END IF;
    UPDATE public.pvp_matchmaking_queue
    SET status = 'searching', claim_token = NULL, updated_at = NOW()
    WHERE claim_token = v_token AND status = 'matching';
    RAISE;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_battle_hub_state(
    p_owner_id BIGINT,
    p_guild_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_queue public.pvp_matchmaking_queue%ROWTYPE;
    v_div TEXT;
    v_pvp_day INTEGER;
    v_prac_day INTEGER;
    v_rivals INTEGER;
    v_run UUID;
BEGIN
    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    SELECT gd.name INTO v_div
    FROM public.global_divisions gd
    WHERE v_player.global_lp >= gd.min_lp
    ORDER BY gd.min_lp DESC
    LIMIT 1;

    SELECT * INTO v_queue
    FROM public.pvp_matchmaking_queue
    WHERE owner_id = p_owner_id AND status IN ('searching', 'matching')
    ORDER BY joined_at DESC
    LIMIT 1;

    SELECT COUNT(*)::INTEGER INTO v_pvp_day
    FROM public.match_history
    WHERE player_id = p_owner_id AND match_type = 'pvp'
      AND (played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;

    SELECT COUNT(*)::INTEGER INTO v_prac_day
    FROM public.match_history
    WHERE player_id = p_owner_id AND match_type = 'practice'
      AND (played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;

    SELECT COUNT(*)::INTEGER INTO v_rivals
    FROM public.manager_rivalries
    WHERE status = 'active'
      AND (manager_a_id = p_owner_id OR manager_b_id = p_owner_id);

    SELECT id INTO v_run
    FROM public.match_runs
    WHERE status IN ('streaming', 'completing')
      AND (home_discord_id = p_owner_id OR away_discord_id = p_owner_id OR active_discord_id = p_owner_id)
    ORDER BY started_at DESC
    LIMIT 1;

    RETURN jsonb_build_object(
        'battle_pvp_enabled', public._pvp_flag_on(),
        'pvp_rewards_enabled', COALESCE((public.get_game_config('pvp_rewards_enabled') #>> '{}')::BOOLEAN, FALSE),
        'pvp_rivalries_enabled', COALESCE((public.get_game_config('pvp_rivalries_enabled') #>> '{}')::BOOLEAN, FALSE),
        'pvp_energy_cost', public.get_game_config_int('pvp_energy_cost', 20),
        'practice_energy_cost', public.get_game_config_int('ai_practice_energy_cost', 10),
        'global_lp', v_player.global_lp,
        'global_division', COALESCE(v_div, 'Unknown'),
        'action_energy', v_player.action_energy,
        'daily_pvp_count', COALESCE(v_pvp_day, 0),
        'daily_pvp_cap', public.get_game_config_int('pvp_rewarded_matches_daily', 5),
        'daily_practice_count', COALESCE(v_prac_day, 0),
        'daily_practice_cap', public.get_game_config_int('ai_practice_rewarded_daily', 2),
        'active_rivalry_count', COALESCE(v_rivals, 0),
        'requeue_available_at', v_player.pvp_requeue_available_at,
        'unresolved_run_id', v_run,
        'queue', CASE WHEN v_queue.id IS NULL THEN NULL ELSE jsonb_build_object(
            'queue_id', v_queue.id,
            'status', v_queue.status,
            'joined_at', v_queue.joined_at,
            'expires_at', v_queue.expires_at,
            'global_lp', v_queue.global_lp,
            'xi_rating', v_queue.xi_rating,
            'global_division', v_queue.global_division
        ) END
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_battle_hub_state(BIGINT, BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._pvp_search_bands(NUMERIC) TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.get_battle_hub_state(bigint,bigint)') IS NULL THEN
        RAISE EXCEPTION '099 guard failed: get_battle_hub_state';
    END IF;
END $$;

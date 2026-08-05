-- Migration 103: Instant PvP Backfill and Ghost Managers (Feature 054)
-- Implements Level 1 (Live Human), Level 2 (Ghost Manager), Level 3 (Calibrated Ranked AI)

-- 1) pvp_ghost_snapshots table
CREATE TABLE IF NOT EXISTS public.pvp_ghost_snapshots (
    owner_id             BIGINT PRIMARY KEY REFERENCES public.players(discord_id) ON DELETE CASCADE,
    club_name            TEXT NOT NULL,
    global_lp            INTEGER NOT NULL,
    global_division      TEXT NOT NULL,
    division_rank        INTEGER NOT NULL,
    xi_rating            NUMERIC(6,2) NOT NULL,
    snapshot_json        JSONB NOT NULL,
    snapshot_schema      INTEGER NOT NULL DEFAULT 1,
    captured_at          TIMESTAMPTZ NOT NULL,
    last_selected_at     TIMESTAMPTZ,
    selection_count      INTEGER NOT NULL DEFAULT 0,
    eligible             BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS for pvp_ghost_snapshots
ALTER TABLE public.pvp_ghost_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pvp_ghost_snapshots_read_anon ON public.pvp_ghost_snapshots;
CREATE POLICY pvp_ghost_snapshots_read_anon ON public.pvp_ghost_snapshots
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS pvp_ghost_snapshots_write_all ON public.pvp_ghost_snapshots;
CREATE POLICY pvp_ghost_snapshots_write_all ON public.pvp_ghost_snapshots
    FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true);

-- Indexes for pvp_ghost_snapshots
CREATE INDEX IF NOT EXISTS idx_pvp_ghost_snapshots_eligibility
    ON public.pvp_ghost_snapshots (eligible, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_pvp_ghost_snapshots_match
    ON public.pvp_ghost_snapshots (eligible, division_rank, global_lp, xi_rating, captured_at);

-- 2) pvp_ghost_encounters table
CREATE TABLE IF NOT EXISTS public.pvp_ghost_encounters (
    run_id               UUID PRIMARY KEY,
    challenger_id        BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    ghost_owner_id       BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    opponent_mode        TEXT NOT NULL CHECK (opponent_mode IN ('ghost', 'ai_backfill')),
    snapshot_captured_at TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS for pvp_ghost_encounters
ALTER TABLE public.pvp_ghost_encounters ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pvp_ghost_encounters_read_anon ON public.pvp_ghost_encounters;
CREATE POLICY pvp_ghost_encounters_read_anon ON public.pvp_ghost_encounters
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS pvp_ghost_encounters_write_all ON public.pvp_ghost_encounters;
CREATE POLICY pvp_ghost_encounters_write_all ON public.pvp_ghost_encounters
    FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true);

-- Indexes for pvp_ghost_encounters
CREATE INDEX IF NOT EXISTS idx_pvp_ghost_encounters_challenger_daily
    ON public.pvp_ghost_encounters (challenger_id, created_at);

CREATE INDEX IF NOT EXISTS idx_pvp_ghost_encounters_cooldown
    ON public.pvp_ghost_encounters (challenger_id, ghost_owner_id, created_at DESC);

-- 3) Schema extensions
ALTER TABLE public.pvp_matchmaking_queue
    ADD COLUMN IF NOT EXISTS backfill_after TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS preferred_mode TEXT NOT NULL DEFAULT 'automatic';

ALTER TABLE public.match_runs
    ADD COLUMN IF NOT EXISTS opponent_mode TEXT NOT NULL DEFAULT 'live';

ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS opponent_mode TEXT NOT NULL DEFAULT 'live',
    ADD COLUMN IF NOT EXISTS opponent_snapshot_age_seconds INTEGER;

-- 4) RPC: refresh_pvp_ghost_snapshot
-- 4) Build Canonical Squad Snapshot RPC with correct column names (player_card_id, position_slot, "def")
CREATE OR REPLACE FUNCTION public.build_pvp_squad_snapshot(
    p_owner_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
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
                'position', pc.position,
                'overall', pc.overall,
                'pac', pc.pac,
                'sho', pc.sho,
                'pas', pc.pas,
                'dri', pc.dri,
                'def_stat', pc."def",
                'phy', pc.phy,
                'morale', COALESCE(pc.morale, 80),
                'playstyles', '[]'::jsonb
            ) ORDER BY sa.position_slot ASC
        ),
        array_agg(pc.id ORDER BY sa.position_slot ASC),
        jsonb_agg(
            jsonb_build_object(
                'id', pc.id,
                'level', COALESCE(pc.level, 1),
                'age', public.card_age_from_dob(pc.date_of_birth),
                'date_of_birth', pc.date_of_birth,
                'fatigue', pc.fatigue,
                'injury_tier', pc.injury_tier,
                'slot', sa.position_slot
            ) ORDER BY sa.position_slot ASC
        ),
        AVG(pc.overall)::NUMERIC
    INTO v_squad, v_ids, v_meta, v_rating
    FROM public.squad_assignments sa
    JOIN public.player_cards pc ON pc.id = sa.player_card_id
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
        'formation', COALESCE((SELECT formation FROM public.squads WHERE discord_id = p_owner_id), '4-3-3'),
        'tactics', jsonb_build_object(
            'formation', COALESCE((SELECT formation FROM public.squads WHERE discord_id = p_owner_id), '4-3-3'),
            'stance', 'balanced',
            'intensity_tier', 2
        ),
        'xi_rating', ROUND(v_rating, 2),
        'squad', v_squad,
        'card_ids', to_jsonb(v_ids),
        'card_meta', v_meta,
        'policies', v_policy
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.refresh_pvp_ghost_snapshot(
    p_owner_id BIGINT,
    p_source_run_id UUID DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_snap JSONB;
    v_div_rank INTEGER;
    v_xi_rating NUMERIC(6,2);
BEGIN
    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'reason', 'player_not_found');
    END IF;

    -- Build canonical snapshot (validates 11 cards)
    BEGIN
        v_snap := public.build_pvp_squad_snapshot(p_owner_id);
    EXCEPTION WHEN OTHERS THEN
        UPDATE public.pvp_ghost_snapshots
        SET eligible = FALSE, updated_at = NOW()
        WHERE owner_id = p_owner_id;
        RETURN jsonb_build_object('success', false, 'reason', 'invalid_squad');
    END;

    v_div_rank := public.pvp_division_rank(v_player.global_lp);
    v_xi_rating := (v_snap ->> 'xi_rating')::NUMERIC(6,2);

    INSERT INTO public.pvp_ghost_snapshots (
        owner_id, club_name, global_lp, global_division, division_rank,
        xi_rating, snapshot_json, snapshot_schema, captured_at, eligible, updated_at
    ) VALUES (
        p_owner_id, v_player.club_name, v_player.global_lp, 'Division ' || v_div_rank, v_div_rank,
        v_xi_rating, v_snap, 1, NOW(), TRUE, NOW()
    )
    ON CONFLICT (owner_id) DO UPDATE SET
        club_name = EXCLUDED.club_name,
        global_lp = EXCLUDED.global_lp,
        global_division = EXCLUDED.global_division,
        division_rank = EXCLUDED.division_rank,
        xi_rating = EXCLUDED.xi_rating,
        snapshot_json = EXCLUDED.snapshot_json,
        captured_at = EXCLUDED.captured_at,
        eligible = TRUE,
        updated_at = NOW();

    RETURN jsonb_build_object(
        'success', true,
        'owner_id', p_owner_id,
        'club_name', v_player.club_name,
        'xi_rating', v_xi_rating,
        'captured_at', NOW()
    );
END;
$$;

-- 5) Helper for Calibrated Ranked AI snapshot construction
CREATE OR REPLACE FUNCTION public.build_calibrated_pvp_ai_snapshot(
    p_target_ovr NUMERIC,
    p_division TEXT DEFAULT 'Professional'
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_base_ovr INTEGER := LEAST(99, GREATEST(40, ROUND(p_target_ovr)::INTEGER));
    v_squad JSONB;
    v_positions TEXT[] := ARRAY['GK', 'CB', 'CB', 'LB', 'RB', 'CM', 'CM', 'CAM', 'LW', 'RW', 'ST'];
    v_pos TEXT;
    i INTEGER;
BEGIN
    v_squad := '[]'::jsonb;
    FOR i IN 1..11 LOOP
        v_pos := v_positions[i];
        v_squad := v_squad || jsonb_build_object(
            'name', p_division || ' AI Player ' || i,
            'position', v_pos,
            'overall', v_base_ovr,
            'pac', v_base_ovr,
            'sho', v_base_ovr,
            'pas', v_base_ovr,
            'dri', v_base_ovr,
            'def_stat', v_base_ovr,
            'phy', v_base_ovr,
            'morale', 85,
            'playstyles', '[]'::jsonb
        );
    END LOOP;

    RETURN jsonb_build_object(
        'owner_id', NULL,
        'club_name', p_division || ' Division XI',
        'formation', '4-3-3',
        'tactics', jsonb_build_object('stance', 'balanced', 'intensity_tier', 2),
        'xi_rating', ROUND(p_target_ovr, 2),
        'squad', v_squad,
        'card_ids', '[]'::jsonb,
        'card_meta', '[]'::jsonb,
        'finalization_policy', jsonb_build_object(
            'economy_enabled', true,
            'xp_enabled', true,
            'fitness_enabled', true,
            'rivalry_enabled', false
        )
    );
END;
$$;

-- 6) Extended try_match_pvp_queue with Level 1 (Live), Level 2 (Ghost), Level 3 (AI Backfill)
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
    v_ghost public.pvp_ghost_snapshots%ROWTYPE;
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
    v_backfill_daily_cap INTEGER;
    v_backfill_count INTEGER;
    v_cost INTEGER;
    v_energy INTEGER;
    v_snap_a JSONB;
    v_snap_b JSONB;
    v_snap_ghost JSONB;
    v_snap_ai JSONB;
    v_full_snap JSONB;
    v_a_rank INTEGER;
    v_backfill_after TIMESTAMPTZ;
    v_backfill_enabled BOOLEAN;
    v_ghost_age INTEGER;
BEGIN
    PERFORM public.expire_pvp_queue_rows();

    IF NOT public._pvp_flag_on() THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'disabled');
    END IF;

    v_backfill_enabled := COALESCE((public.get_game_config('pvp_backfill_enabled') #>> '{}')::BOOLEAN, TRUE);
    v_cooldown_min := public.get_game_config_int('pvp_same_pair_cooldown_minutes', 30)::INTEGER;
    v_pair_daily := public.get_game_config_int('pvp_same_pair_matches_daily', 2)::INTEGER;
    v_mgr_daily := public.get_game_config_int('pvp_rewarded_matches_daily', 5)::INTEGER;
    v_backfill_daily_cap := public.get_game_config_int('pvp_backfill_daily_limit', 3)::INTEGER;
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

    -- Set backfill_after if null (default 10s after joined_at)
    IF v_a.backfill_after IS NULL THEN
        v_backfill_after := v_a.joined_at + INTERVAL '10 seconds';
        UPDATE public.pvp_matchmaking_queue
        SET backfill_after = v_backfill_after
        WHERE id = v_a.id;
        v_a.backfill_after := v_backfill_after;
    END IF;

    v_wait := EXTRACT(EPOCH FROM (NOW() - v_a.joined_at));
    SELECT max_div_diff, max_lp, max_ovr INTO v_max_div, v_max_lp, v_max_ovr
    FROM public._pvp_search_bands(v_wait);

    v_a_rank := public.pvp_division_rank(v_a.global_lp);

    -- Level 1: Find eligible live human candidate B
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

    -- If live human opponent found, pair live match!
    IF FOUND THEN
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
            sim_seed, squad_snapshot, guild_id, channel_id, opponent_mode
        ) VALUES (
            'pvp', 'streaming', v_a.owner_id, v_b.owner_id, v_a.owner_id,
            v_seed, v_full_snap, v_a.guild_id, v_a.channel_id, 'live'
        ) RETURNING id INTO v_run_id;

        UPDATE public.pvp_matchmaking_queue
        SET status = 'matched', matched_run_id = v_run_id, updated_at = NOW()
        WHERE id IN (v_a.id, v_b.id);

        RETURN jsonb_build_object(
            'matched', true,
            'run_id', v_run_id,
            'home_discord_id', v_a.owner_id,
            'away_discord_id', v_b.owner_id,
            'opponent_mode', 'live'
        );
    END IF;

    -- Live human not found. Check if searcher has reached backfill_after threshold
    IF NOT v_backfill_enabled OR NOW() < v_a.backfill_after THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'no_partner', 'queue_id', v_a.id);
    END IF;

    -- Check challenger daily backfill cap
    SELECT COUNT(*) INTO v_backfill_count
    FROM public.pvp_ghost_encounters
    WHERE challenger_id = v_a.owner_id
      AND (created_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;

    IF v_backfill_count >= v_backfill_daily_cap THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'backfill_daily_cap_reached', 'queue_id', v_a.id);
    END IF;

    -- Revalidate challenger energy
    PERFORM public.sync_action_energy(v_a.owner_id);
    SELECT action_energy INTO v_energy FROM public.players WHERE discord_id = v_a.owner_id;
    IF COALESCE(v_energy, 0) < v_cost THEN
        UPDATE public.pvp_matchmaking_queue
        SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
        WHERE id = v_a.id;
        RETURN jsonb_build_object('matched', false, 'reason', 'energy_a');
    END IF;

    BEGIN
        v_snap_a := public.build_pvp_squad_snapshot(v_a.owner_id);
    EXCEPTION WHEN OTHERS THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'xi_invalid');
    END;

    -- Level 2: Select eligible Ghost Manager snapshot
    SELECT gs.* INTO v_ghost
    FROM public.pvp_ghost_snapshots gs
    WHERE gs.eligible = TRUE
      AND gs.owner_id <> v_a.owner_id
      AND gs.captured_at >= NOW() - INTERVAL '7 days'
      AND ABS(gs.division_rank - v_a_rank) <= 2
      AND ABS(gs.global_lp - v_a.global_lp) <= 500
      AND ABS(gs.xi_rating - v_a.xi_rating) <= 12
      -- Blocks check
      AND NOT EXISTS (
          SELECT 1 FROM public.pvp_blocks blk
          WHERE (blk.blocker_id = v_a.owner_id AND blk.blocked_id = gs.owner_id)
             OR (blk.blocker_id = gs.owner_id AND blk.blocked_id = v_a.owner_id)
      )
      -- 24-hour ghost encounter cooldown check
      AND NOT EXISTS (
          SELECT 1 FROM public.pvp_ghost_encounters ge
          WHERE ge.challenger_id = v_a.owner_id
            AND ge.ghost_owner_id = gs.owner_id
            AND ge.created_at > NOW() - INTERVAL '24 hours'
      )
      -- 7-day encounter limit check (max 2)
      AND (
          SELECT COUNT(*) FROM public.pvp_ghost_encounters ge
          WHERE ge.challenger_id = v_a.owner_id
            AND ge.ghost_owner_id = gs.owner_id
            AND ge.created_at > NOW() - INTERVAL '7 days'
      ) < 2
    ORDER BY
        ABS(gs.division_rank - v_a_rank) ASC,
        ABS(gs.xi_rating - v_a.xi_rating) ASC,
        ABS(gs.global_lp - v_a.global_lp) ASC,
        gs.captured_at DESC,
        gs.last_selected_at ASC NULLS FIRST,
        gs.selection_count ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    -- If Ghost snapshot found, create Ghost Match!
    IF FOUND THEN
        IF NOT public.acquire_match_lock(v_a.owner_id, 'pvp') THEN
            RETURN jsonb_build_object('matched', false, 'reason', 'lock_failed');
        END IF;

        v_snap_ghost := v_ghost.snapshot_json;
        v_seed := (floor(random() * 9223372036854775807))::BIGINT;
        v_ghost_age := EXTRACT(EPOCH FROM (NOW() - v_ghost.captured_at))::INTEGER;

        v_full_snap := jsonb_build_object(
            'home_owner_id', v_a.owner_id,
            'away_owner_id', v_ghost.owner_id,
            'away_club_name', v_ghost.club_name,
            'home_xi_rating', v_a.xi_rating,
            'away_xi_rating', v_ghost.xi_rating,
            'home_lp', v_a.global_lp,
            'away_lp', v_ghost.global_lp,
            'home_formation', v_snap_a #>> '{formation}',
            'away_formation', v_snap_ghost #>> '{formation}',
            'home_tactics', v_snap_a -> 'tactics',
            'away_tactics', v_snap_ghost -> 'tactics',
            'home_squad', v_snap_a -> 'squad',
            'away_squad', v_snap_ghost -> 'squad',
            'home_card_ids', v_snap_a -> 'card_ids',
            'away_card_ids', v_snap_ghost -> 'card_ids',
            'home_card_meta', v_snap_a -> 'card_meta',
            'away_card_meta', v_snap_ghost -> 'card_meta',
            'ghost_snapshot_age_seconds', v_ghost_age,
            'finalization_policy', v_snap_a -> 'finalization_policy'
        );

        INSERT INTO public.match_runs (
            run_type, status, home_discord_id, away_discord_id, active_discord_id,
            sim_seed, squad_snapshot, guild_id, channel_id, opponent_mode
        ) VALUES (
            'pvp', 'streaming', v_a.owner_id, v_ghost.owner_id, v_a.owner_id,
            v_seed, v_full_snap, v_a.guild_id, v_a.channel_id, 'ghost'
        ) RETURNING id INTO v_run_id;

        INSERT INTO public.pvp_ghost_encounters (
            run_id, challenger_id, ghost_owner_id, opponent_mode, snapshot_captured_at
        ) VALUES (
            v_run_id, v_a.owner_id, v_ghost.owner_id, 'ghost', v_ghost.captured_at
        );

        UPDATE public.pvp_ghost_snapshots
        SET last_selected_at = NOW(), selection_count = selection_count + 1, updated_at = NOW()
        WHERE owner_id = v_ghost.owner_id;

        UPDATE public.pvp_matchmaking_queue
        SET status = 'matched', matched_run_id = v_run_id, updated_at = NOW()
        WHERE id = v_a.id;

        RETURN jsonb_build_object(
            'matched', true,
            'run_id', v_run_id,
            'home_discord_id', v_a.owner_id,
            'away_discord_id', v_ghost.owner_id,
            'opponent_mode', 'ghost',
            'ghost_snapshot_age_seconds', v_ghost_age
        );
    END IF;

    -- Level 3: Calibrated Ranked AI Fallback
    IF NOT public.acquire_match_lock(v_a.owner_id, 'pvp') THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'lock_failed');
    END IF;

    v_snap_ai := public.build_calibrated_pvp_ai_snapshot(v_a.xi_rating, COALESCE(v_a.global_division, 'Professional'));
    v_seed := (floor(random() * 9223372036854775807))::BIGINT;

    v_full_snap := jsonb_build_object(
        'home_owner_id', v_a.owner_id,
        'away_owner_id', NULL,
        'away_club_name', v_snap_ai ->> 'club_name',
        'home_xi_rating', v_a.xi_rating,
        'away_xi_rating', v_a.xi_rating,
        'home_lp', v_a.global_lp,
        'away_lp', v_a.global_lp,
        'home_formation', v_snap_a #>> '{formation}',
        'away_formation', v_snap_ai #>> '{formation}',
        'home_tactics', v_snap_a -> 'tactics',
        'away_tactics', v_snap_ai -> 'tactics',
        'home_squad', v_snap_a -> 'squad',
        'away_squad', v_snap_ai -> 'squad',
        'home_card_ids', v_snap_a -> 'card_ids',
        'away_card_ids', '[]'::jsonb,
        'home_card_meta', v_snap_a -> 'card_meta',
        'away_card_meta', '[]'::jsonb,
        'finalization_policy', v_snap_a -> 'finalization_policy'
    );

    INSERT INTO public.match_runs (
        run_type, status, home_discord_id, away_discord_id, active_discord_id,
        sim_seed, squad_snapshot, guild_id, channel_id, opponent_mode
    ) VALUES (
        'pvp', 'streaming', v_a.owner_id, NULL, v_a.owner_id,
        v_seed, v_full_snap, v_a.guild_id, v_a.channel_id, 'ai_backfill'
    ) RETURNING id INTO v_run_id;

    INSERT INTO public.pvp_ghost_encounters (
        run_id, challenger_id, ghost_owner_id, opponent_mode, snapshot_captured_at
    ) VALUES (
        v_run_id, v_a.owner_id, NULL, 'ai_backfill', NULL
    );

    UPDATE public.pvp_matchmaking_queue
    SET status = 'matched', matched_run_id = v_run_id, updated_at = NOW()
    WHERE id = v_a.id;

    RETURN jsonb_build_object(
        'matched', true,
        'run_id', v_run_id,
        'home_discord_id', v_a.owner_id,
        'away_discord_id', NULL,
        'opponent_mode', 'ai_backfill'
    );
END;
$$;

-- 7) Extended finalize_pvp_match supporting live, ghost, and ai_backfill modes
DROP FUNCTION IF EXISTS public.finalize_pvp_match(UUID, INTEGER, INTEGER, NUMERIC, NUMERIC);
CREATE OR REPLACE FUNCTION public.finalize_pvp_match(
    p_run_id UUID,
    p_home_score INTEGER,
    p_away_score INTEGER,
    p_home_rating NUMERIC DEFAULT NULL,
    p_away_rating NUMERIC DEFAULT NULL
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
    v_opp_mode TEXT;
    v_coin_mult NUMERIC := 1.0;
    v_pos_lp_mult NUMERIC := 1.0;
    v_neg_lp_mult NUMERIC := 1.0;
    v_xp_mult NUMERIC := 1.0;
    v_snap_age INTEGER;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Match run % not found', p_run_id;
    END IF;

    v_opp_mode := COALESCE(v_run.opponent_mode, 'live');

    IF v_run.status IN ('completing', 'completed') THEN
        SELECT id INTO v_hist_home FROM public.match_history WHERE run_id = p_run_id AND player_id = v_run.home_discord_id;
        IF v_opp_mode = 'live' AND v_run.away_discord_id IS NOT NULL THEN
            SELECT id INTO v_hist_away FROM public.match_history WHERE run_id = p_run_id AND player_id = v_run.away_discord_id;
        END IF;
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

    v_policy := COALESCE(v_run.squad_snapshot -> 'finalization_policy', '{}'::jsonb);
    v_rewards := COALESCE((v_policy #>> '{economy_enabled}')::BOOLEAN, TRUE);
    v_rivalries := COALESCE((v_policy #>> '{rivalry_enabled}')::BOOLEAN, TRUE);

    -- Rivalries only apply for live human matches
    IF v_opp_mode <> 'live' THEN
        v_rivalries := FALSE;
    END IF;

    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;
    v_prov := public.get_game_config_int('pvp_provisional_matches', 5)::INTEGER;

    v_home_res := CASE WHEN p_home_score > p_away_score THEN 'win' WHEN p_home_score < p_away_score THEN 'loss' ELSE 'draw' END;
    v_away_res := CASE WHEN p_away_score > p_home_score THEN 'win' WHEN p_away_score < p_home_score THEN 'loss' ELSE 'draw' END;

    -- Multipliers by mode
    IF v_opp_mode = 'ghost' THEN
        v_coin_mult := 0.85;
        v_pos_lp_mult := 0.75;
        v_neg_lp_mult := 0.50;
    ELSIF v_opp_mode = 'ai_backfill' THEN
        v_coin_mult := 0.70;
        v_pos_lp_mult := 0.50;
        v_neg_lp_mult := 0.25;
    END IF;

    v_mult_win := public.get_game_config_numeric('pvp_coin_multiplier_win', 1.25);
    v_mult_draw := public.get_game_config_numeric('pvp_coin_multiplier_draw', 1.10);
    v_mult_loss := public.get_game_config_numeric('pvp_coin_multiplier_loss', 1.00);

    -- Apply Challenger Rewards
    IF v_rewards THEN
        PERFORM public.apply_club_economy(v_home.discord_id, 0, -v_cost, 'pvp_energy', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));

        v_home_coins := ROUND(100 * (CASE v_home_res WHEN 'win' THEN v_mult_win WHEN 'draw' THEN v_mult_draw ELSE v_mult_loss END) * v_coin_mult)::INTEGER;
        PERFORM public.apply_club_economy(v_home.discord_id, v_home_coins, 0, 'pvp_reward', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));

        v_raw_lp := CASE v_home_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_home_res = 'loss' AND COALESCE(v_home.pvp_ranked_matches, 0) < v_prov THEN
            v_raw_lp := v_raw_lp / 2;
        END IF;

        IF v_raw_lp >= 0 THEN
            v_raw_lp := ROUND(v_raw_lp * v_pos_lp_mult)::INTEGER;
        ELSE
            v_raw_lp := ROUND(v_raw_lp * v_neg_lp_mult)::INTEGER;
        END IF;

        v_new_lp := GREATEST(0, v_home.global_lp + v_raw_lp);
        v_home_lp := v_new_lp - v_home.global_lp;

        PERFORM public.increment_match_career_stats(v_home.discord_id, v_home_res, CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END, v_home_lp, p_home_score - p_away_score);
        UPDATE public.players SET pvp_ranked_matches = COALESCE(pvp_ranked_matches, 0) + 1 WHERE discord_id = v_home.discord_id;
    END IF;

    v_snap_age := (v_run.squad_snapshot ->> 'ghost_snapshot_age_seconds')::INTEGER;

    -- Challenger match history row
    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted, opponent_mode, opponent_snapshot_age_seconds
    ) VALUES (
        v_home.discord_id, v_home_res, p_home_rating, p_away_rating,
        p_home_score, p_away_score, v_home_coins,
        CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_run.away_discord_id, 'pvp', v_home_lp, v_rivalries,
        v_opp_mode, v_snap_age
    ) ON CONFLICT (run_id, player_id) WHERE run_id IS NOT NULL DO UPDATE SET run_id = EXCLUDED.run_id
    RETURNING id INTO v_hist_home;

    -- If LIVE mode, process away manager rewards & history row
    IF v_opp_mode = 'live' AND v_run.away_discord_id IS NOT NULL THEN
        SELECT * INTO v_away FROM public.players WHERE discord_id = v_run.away_discord_id FOR UPDATE;

        IF v_rewards THEN
            PERFORM public.apply_club_economy(v_away.discord_id, 0, -v_cost, 'pvp_energy', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));

            v_away_coins := ROUND(100 * CASE v_away_res WHEN 'win' THEN v_mult_win WHEN 'draw' THEN v_mult_draw ELSE v_mult_loss END)::INTEGER;
            PERFORM public.apply_club_economy(v_away.discord_id, v_away_coins, 0, 'pvp_reward', p_run_id::TEXT, jsonb_build_object('match_type', 'pvp'));

            v_raw_lp := CASE v_away_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
            IF v_away_res = 'loss' AND COALESCE(v_away.pvp_ranked_matches, 0) < v_prov THEN v_raw_lp := v_raw_lp / 2; END IF;
            v_new_lp := GREATEST(0, v_away.global_lp + v_raw_lp);
            v_away_lp := v_new_lp - v_away.global_lp;

            PERFORM public.increment_match_career_stats(v_away.discord_id, v_away_res, CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END, v_away_lp, p_away_score - p_home_score);
            UPDATE public.players SET pvp_ranked_matches = COALESCE(pvp_ranked_matches, 0) + 1 WHERE discord_id = v_away.discord_id;
        END IF;

        INSERT INTO public.match_history (
            player_id, result, my_rating, opponent_rating, goals_for, goals_against,
            coins_earned, points_earned, run_id, opponent_owner_id, match_type,
            global_lp_delta, rivalry_counted, opponent_mode
        ) VALUES (
            v_away.discord_id, v_away_res, p_away_rating, p_home_rating,
            p_away_score, p_home_score, v_away_coins,
            CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
            p_run_id, v_home.discord_id, 'pvp', v_away_lp, v_rivalries, 'live'
        ) ON CONFLICT (run_id, player_id) WHERE run_id IS NOT NULL DO UPDATE SET run_id = EXCLUDED.run_id
        RETURNING id INTO v_hist_away;

        IF v_rivalries THEN
            v_rivalry := public._upsert_rivalry_from_pvp(v_home.discord_id, v_away.discord_id, p_home_score, p_away_score);
        END IF;
    END IF;

    -- Refresh challenger's ghost snapshot
    PERFORM public.refresh_pvp_ghost_snapshot(v_home.discord_id, p_run_id);

    -- Mark status completing (holds locks until complete_pvp_run)
    UPDATE public.match_runs SET
        status = 'completing', home_score = p_home_score, away_score = p_away_score,
        last_minute = 90, completion_key = p_run_id::TEXT, updated_at = NOW()
    WHERE id = p_run_id;

    RETURN jsonb_build_object(
        'ok', true,
        'run_id', p_run_id,
        'opponent_mode', v_opp_mode,
        'rewards_skipped', NOT v_rewards,
        'rivalry', v_rivalry,
        'home', jsonb_build_object('owner_id', v_home.discord_id, 'result', v_home_res, 'coins', v_home_coins, 'lp_delta', v_home_lp, 'history_id', v_hist_home, 'rating', p_home_rating),
        'away', jsonb_build_object('owner_id', v_run.away_discord_id, 'result', v_away_res, 'coins', v_away_coins, 'lp_delta', v_away_lp, 'history_id', v_hist_away, 'rating', p_away_rating)
    );
END;
$$;

-- 8) Extended get_battle_hub_state with daily_backfill_count and daily_backfill_cap
CREATE OR REPLACE FUNCTION public.get_battle_hub_state(
    p_owner_id BIGINT,
    p_guild_id BIGINT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_queue public.pvp_matchmaking_queue%ROWTYPE;
    v_div TEXT;
    v_pvp_day INTEGER;
    v_prac_day INTEGER;
    v_backfill_day INTEGER;
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

    SELECT COUNT(*)::INTEGER INTO v_backfill_day
    FROM public.pvp_ghost_encounters
    WHERE challenger_id = p_owner_id
      AND (created_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;

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
        'pvp_backfill_enabled', COALESCE((public.get_game_config('pvp_backfill_enabled') #>> '{}')::BOOLEAN, TRUE),
        'pvp_rewards_enabled', COALESCE((public.get_game_config('pvp_rewards_enabled') #>> '{}')::BOOLEAN, FALSE),
        'pvp_rivalries_enabled', COALESCE((public.get_game_config('pvp_rivalries_enabled') #>> '{}')::BOOLEAN, FALSE),
        'pvp_energy_cost', public.get_game_config_int('pvp_energy_cost', 20),
        'practice_energy_cost', public.get_game_config_int('ai_practice_energy_cost', 10),
        'global_lp', v_player.global_lp,
        'global_division', COALESCE(v_div, 'Unknown'),
        'action_energy', v_player.action_energy,
        'daily_pvp_count', COALESCE(v_pvp_day, 0),
        'daily_pvp_cap', public.get_game_config_int('pvp_rewarded_matches_daily', 5),
        'daily_backfill_count', COALESCE(v_backfill_day, 0),
        'daily_backfill_cap', public.get_game_config_int('pvp_backfill_daily_limit', 3),
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

-- Operational Bootstrap: Populate ghost snapshots for all active human managers
CREATE OR REPLACE FUNCTION public.bootstrap_pvp_ghost_snapshots()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rec RECORD;
    v_count INTEGER := 0;
BEGIN
    FOR v_rec IN
        SELECT DISTINCT p.discord_id
        FROM public.players p
        JOIN public.player_cards pc ON pc.owner_id = p.discord_id
        WHERE pc.is_active = TRUE
        GROUP BY p.discord_id
        HAVING COUNT(pc.id) = 11
    LOOP
        BEGIN
            PERFORM public.refresh_pvp_ghost_snapshot(v_rec.discord_id);
            v_count := v_count + 1;
        EXCEPTION WHEN OTHERS THEN
            NULL; -- Skip any invalid rosters
        END;
    END LOOP;

    RETURN v_count;
END;
$$;

-- Bulk Refresh: Refreshes snapshots for all managers whose snapshot is older than p_max_age_hours
CREATE OR REPLACE FUNCTION public.refresh_all_pvp_ghost_snapshots(p_max_age_hours INTEGER DEFAULT 24)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rec RECORD;
    v_count INTEGER := 0;
BEGIN
    FOR v_rec IN
        SELECT gs.owner_id
        FROM public.pvp_ghost_snapshots gs
        WHERE gs.captured_at < NOW() - (p_max_age_hours || ' hours')::INTERVAL
    LOOP
        BEGIN
            PERFORM public.refresh_pvp_ghost_snapshot(v_rec.owner_id);
            v_count := v_count + 1;
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END LOOP;

    RETURN v_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.bootstrap_pvp_ghost_snapshots() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.refresh_all_pvp_ghost_snapshots(INTEGER) TO anon, authenticated, service_role;

-- 9) Schema guard block
DO $$
DECLARE
    req TEXT;
    reqs TEXT[] := ARRAY[
        'table:public.pvp_ghost_snapshots',
        'table:public.pvp_ghost_encounters',
        'column:public.pvp_matchmaking_queue.backfill_after',
        'column:public.pvp_matchmaking_queue.preferred_mode',
        'column:public.match_runs.opponent_mode',
        'column:public.match_history.opponent_mode',
        'column:public.match_history.opponent_snapshot_age_seconds',
        'function:public.refresh_pvp_ghost_snapshot',
        'function:public.bootstrap_pvp_ghost_snapshots',
        'function:public.refresh_all_pvp_ghost_snapshots',
        'function:public.try_match_pvp_queue',
        'function:public.finalize_pvp_match',
        'policy:public.pvp_ghost_snapshots.pvp_ghost_snapshots_read_anon',
        'policy:public.pvp_ghost_encounters.pvp_ghost_encounters_read_anon'
    ];
BEGIN
    FOREACH req IN ARRAY reqs LOOP
        IF split_part(req, ':', 1) = 'table' THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = split_part(split_part(req, ':', 2), '.', 1)
                  AND table_name = split_part(split_part(req, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing table %', req;
            END IF;
        ELSIF split_part(req, ':', 1) = 'column' THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = split_part(split_part(req, ':', 2), '.', 1)
                  AND table_name = split_part(split_part(req, ':', 2), '.', 2)
                  AND column_name = split_part(split_part(req, ':', 2), '.', 3)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing column %', req;
            END IF;
        ELSIF split_part(req, ':', 1) = 'function' THEN
            IF NOT EXISTS (
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = split_part(split_part(req, ':', 2), '.', 1)
                  AND p.proname = split_part(split_part(req, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing function %', req;
            END IF;
        ELSIF split_part(req, ':', 1) = 'policy' THEN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = split_part(split_part(req, ':', 2), '.', 1)
                  AND tablename = split_part(split_part(req, ':', 2), '.', 2)
                  AND policyname = split_part(split_part(req, ':', 2), '.', 3)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing policy %', req;
            END IF;
        END IF;
    END LOOP;
END;
$$;

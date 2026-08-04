-- Feature 053: Ranked PvP matchmaking + rivalry schema spine
-- Flag battle_pvp_enabled defaults FALSE (dark ship).
-- US-42.4 / US-42.7 / US-42.9

-- ---------------------------------------------------------------------------
-- 1) Extend match_runs.run_type + match_locks.lock_type
-- ---------------------------------------------------------------------------
ALTER TABLE public.match_runs DROP CONSTRAINT IF EXISTS match_runs_run_type_check;
ALTER TABLE public.match_runs
    ADD CONSTRAINT match_runs_run_type_check
    CHECK (run_type IN ('bot', 'friendly', 'league', 'pvp', 'practice'));

ALTER TABLE public.match_locks DROP CONSTRAINT IF EXISTS match_locks_lock_type_check;
ALTER TABLE public.match_locks
    ADD CONSTRAINT match_locks_lock_type_check
    CHECK (lock_type IN ('friendly', 'league', 'bot', 'pvp', 'practice'));

CREATE OR REPLACE FUNCTION public.acquire_match_lock(
    p_discord_id BIGINT,
    p_lock_type TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_inserted BIGINT;
BEGIN
    IF p_lock_type NOT IN ('friendly', 'league', 'bot', 'pvp', 'practice') THEN
        RAISE EXCEPTION 'Invalid lock_type: %', p_lock_type;
    END IF;
    INSERT INTO public.match_locks (discord_id, lock_type)
    VALUES (p_discord_id, p_lock_type)
    ON CONFLICT (discord_id) DO NOTHING
    RETURNING discord_id INTO v_inserted;
    RETURN v_inserted IS NOT NULL;
END;
$$;

-- ---------------------------------------------------------------------------
-- 2) match_history competitive columns
-- ---------------------------------------------------------------------------
ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS opponent_owner_id BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS match_type TEXT,
    ADD COLUMN IF NOT EXISTS global_lp_delta INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rivalry_counted BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE public.match_history
SET match_type = COALESCE(match_type, 'bot')
WHERE match_type IS NULL;

ALTER TABLE public.match_history
    ALTER COLUMN match_type SET DEFAULT 'bot',
    ALTER COLUMN match_type SET NOT NULL;

ALTER TABLE public.match_history DROP CONSTRAINT IF EXISTS match_history_match_type_check;
ALTER TABLE public.match_history
    ADD CONSTRAINT match_history_match_type_check
    CHECK (match_type IN ('pvp', 'practice', 'friendly', 'league', 'bot'));

ALTER TABLE public.match_history DROP CONSTRAINT IF EXISTS match_history_lp_mode_guard;
ALTER TABLE public.match_history
    ADD CONSTRAINT match_history_lp_mode_guard
    CHECK (
        (match_type = 'pvp')
        OR (global_lp_delta = 0 AND rivalry_counted = FALSE)
    );

-- ---------------------------------------------------------------------------
-- 3) Player PvP prefs / badges / requeue
-- ---------------------------------------------------------------------------
ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS pvp_rivalry_dms BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS pvp_rivalry_callouts BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS pvp_rivalry_lb_visible BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS pvp_badge_keys TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS pvp_requeue_available_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS pvp_ranked_matches INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- 4) Queue / rivalry / blocks tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pvp_matchmaking_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    guild_id        BIGINT NOT NULL,
    channel_id      BIGINT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('searching', 'matching', 'matched', 'cancelled', 'expired')),
    global_division TEXT NOT NULL,
    global_lp       INTEGER NOT NULL CHECK (global_lp >= 0),
    xi_rating       NUMERIC(6, 2) NOT NULL,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    matched_run_id  UUID REFERENCES public.match_runs(id) ON DELETE SET NULL,
    claim_token     UUID,
    cancelled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pvp_queue_one_active
    ON public.pvp_matchmaking_queue (owner_id)
    WHERE status IN ('searching', 'matching');

CREATE INDEX IF NOT EXISTS idx_pvp_queue_guild_status_joined
    ON public.pvp_matchmaking_queue (guild_id, status, joined_at);

CREATE INDEX IF NOT EXISTS idx_pvp_queue_owner_status
    ON public.pvp_matchmaking_queue (owner_id, status);

CREATE TABLE IF NOT EXISTS public.manager_rivalries (
    manager_a_id            BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    manager_b_id            BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    meetings                INTEGER NOT NULL DEFAULT 0 CHECK (meetings >= 0),
    a_wins                  INTEGER NOT NULL DEFAULT 0 CHECK (a_wins >= 0),
    b_wins                  INTEGER NOT NULL DEFAULT 0 CHECK (b_wins >= 0),
    draws                   INTEGER NOT NULL DEFAULT 0 CHECK (draws >= 0),
    a_goals                 INTEGER NOT NULL DEFAULT 0 CHECK (a_goals >= 0),
    b_goals                 INTEGER NOT NULL DEFAULT 0 CHECK (b_goals >= 0),
    current_streak_owner    BIGINT,
    current_streak_count    INTEGER NOT NULL DEFAULT 0 CHECK (current_streak_count >= 0),
    longest_streak_owner    BIGINT,
    longest_streak_count    INTEGER NOT NULL DEFAULT 0 CHECK (longest_streak_count >= 0),
    last_winner_id          BIGINT,
    last_result             TEXT,
    activated_at            TIMESTAMPTZ,
    last_match_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_meeting_in_window_at TIMESTAMPTZ,
    status                  TEXT NOT NULL DEFAULT 'tracking'
                            CHECK (status IN ('tracking', 'active', 'dormant')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (manager_a_id, manager_b_id),
    CHECK (manager_a_id < manager_b_id)
);

CREATE TABLE IF NOT EXISTS public.pvp_blocks (
    blocker_id  BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    blocked_id  BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id <> blocked_id)
);

ALTER TABLE public.pvp_matchmaking_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.manager_rivalries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pvp_blocks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pvp_queue_select ON public.pvp_matchmaking_queue;
CREATE POLICY pvp_queue_select ON public.pvp_matchmaking_queue
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS manager_rivalries_select ON public.manager_rivalries;
CREATE POLICY manager_rivalries_select ON public.manager_rivalries
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS pvp_blocks_select ON public.pvp_blocks;
CREATE POLICY pvp_blocks_select ON public.pvp_blocks
    FOR SELECT TO anon, authenticated, service_role USING (true);

-- Mutations via RPC / service_role only (no anon INSERT/UPDATE/DELETE policies)

GRANT SELECT ON public.pvp_matchmaking_queue TO anon, authenticated, service_role;
GRANT SELECT ON public.manager_rivalries TO anon, authenticated, service_role;
GRANT SELECT ON public.pvp_blocks TO anon, authenticated, service_role;
GRANT ALL ON public.pvp_matchmaking_queue TO service_role;
GRANT ALL ON public.manager_rivalries TO service_role;
GRANT ALL ON public.pvp_blocks TO service_role;

-- ---------------------------------------------------------------------------
-- 5) game_config seeds (flag OFF)
-- ---------------------------------------------------------------------------
INSERT INTO public.game_config (key, value_json) VALUES
    ('battle_pvp_enabled', 'false'),
    ('pvp_rewards_enabled', 'false'),
    ('pvp_rivalries_enabled', 'false'),
    ('pvp_rivalry_dms_enabled', 'true'),
    ('pvp_server_leaderboard_enabled', 'true'),
    ('ai_practice_rewards_enabled', 'true'),
    ('pvp_search_timeout_seconds', '60'),
    ('pvp_matchmaker_interval_seconds', '5'),
    ('pvp_energy_cost', '20'),
    ('pvp_rewarded_matches_daily', '5'),
    ('pvp_same_pair_cooldown_minutes', '30'),
    ('pvp_same_pair_matches_daily', '2'),
    ('pvp_initial_lp_range', '100'),
    ('pvp_initial_ovr_range', '4'),
    ('pvp_max_lp_range', '500'),
    ('pvp_max_ovr_range', '12'),
    ('pvp_provisional_matches', '5'),
    ('pvp_coin_multiplier_win', '1.25'),
    ('pvp_coin_multiplier_draw', '1.10'),
    ('pvp_coin_multiplier_loss', '1.00'),
    ('ai_practice_energy_cost', '10'),
    ('ai_practice_new_manager_reward_multiplier', '0.75'),
    ('ai_practice_established_reward_multiplier', '0.50'),
    ('ai_practice_rewarded_daily', '2'),
    ('pvp_rivalry_activation_matches', '3'),
    ('pvp_rivalry_activation_days', '30'),
    ('pvp_rivalry_dormant_days', '60'),
    ('match_engine_v3_pvp', '0'),
    ('match_engine_v3_practice', '0'),
    ('match_energy_pvp', '20'),
    ('match_energy_practice', '10')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 6) Helpers + queue RPCs
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public._pvp_flag_on()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE((public.get_game_config('battle_pvp_enabled') #>> '{}')::BOOLEAN, FALSE);
$$;

CREATE OR REPLACE FUNCTION public.expire_pvp_queue_rows()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_n INTEGER;
BEGIN
    UPDATE public.pvp_matchmaking_queue
    SET status = 'expired', updated_at = NOW()
    WHERE status = 'searching'
      AND expires_at < NOW();
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN v_n;
END;
$$;

CREATE OR REPLACE FUNCTION public.join_pvp_queue(
    p_owner_id BIGINT,
    p_guild_id BIGINT,
    p_channel_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_energy INTEGER;
    v_cost INTEGER;
    v_xi INTEGER;
    v_ovr NUMERIC;
    v_div TEXT;
    v_timeout INTEGER;
    v_daily_cap INTEGER;
    v_daily_count INTEGER;
    v_row public.pvp_matchmaking_queue%ROWTYPE;
BEGIN
    PERFORM public.expire_pvp_queue_rows();

    IF NOT public._pvp_flag_on() THEN
        RAISE EXCEPTION 'PvP matchmaking is disabled';
    END IF;

    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    IF v_player.pvp_requeue_available_at IS NOT NULL
       AND v_player.pvp_requeue_available_at > NOW() THEN
        RAISE EXCEPTION 'Requeue delay active — wait a few seconds';
    END IF;

    IF EXISTS (SELECT 1 FROM public.match_locks WHERE discord_id = p_owner_id) THEN
        RAISE EXCEPTION 'Already in an active match';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.pvp_matchmaking_queue
        WHERE owner_id = p_owner_id AND status IN ('searching', 'matching')
    ) THEN
        RAISE EXCEPTION 'Already searching for an opponent';
    END IF;

    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;
    PERFORM public.sync_action_energy(p_owner_id);
    SELECT action_energy INTO v_energy FROM public.players WHERE discord_id = p_owner_id;
    IF COALESCE(v_energy, 0) < v_cost THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    SELECT COUNT(*)::INTEGER, COALESCE(AVG(pc.overall), 0)
    INTO v_xi, v_ovr
    FROM public.squad_assignments sa
    JOIN public.player_cards pc ON pc.id = sa.player_card_id
    WHERE sa.discord_id = p_owner_id;

    IF v_xi <> 11 OR COALESCE(v_player.squad_invalid, FALSE) THEN
        RAISE EXCEPTION 'Starting XI is invalid — need 11 eligible players';
    END IF;

    v_daily_cap := public.get_game_config_int('pvp_rewarded_matches_daily', 5)::INTEGER;
    SELECT COUNT(*)::INTEGER INTO v_daily_count
    FROM public.match_history
    WHERE player_id = p_owner_id
      AND match_type = 'pvp'
      AND (played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;
    IF v_daily_count >= v_daily_cap THEN
        RAISE EXCEPTION 'Daily ranked PvP limit reached';
    END IF;

    SELECT gd.name INTO v_div
    FROM public.global_divisions gd
    WHERE v_player.global_lp >= gd.min_lp
    ORDER BY gd.min_lp DESC
    LIMIT 1;
    v_div := COALESCE(v_div, 'Unknown');

    v_timeout := public.get_game_config_int('pvp_search_timeout_seconds', 60)::INTEGER;

    INSERT INTO public.pvp_matchmaking_queue (
        owner_id, guild_id, channel_id, status,
        global_division, global_lp, xi_rating,
        joined_at, expires_at
    ) VALUES (
        p_owner_id, p_guild_id, p_channel_id, 'searching',
        v_div, v_player.global_lp, ROUND(v_ovr, 2),
        NOW(), NOW() + make_interval(secs => v_timeout)
    )
    RETURNING * INTO v_row;

    RETURN jsonb_build_object(
        'queue_id', v_row.id,
        'status', v_row.status,
        'global_division', v_row.global_division,
        'global_lp', v_row.global_lp,
        'xi_rating', v_row.xi_rating,
        'joined_at', v_row.joined_at,
        'expires_at', v_row.expires_at,
        'energy_spent', 0
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.cancel_pvp_queue(
    p_owner_id BIGINT,
    p_queue_id UUID DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_row public.pvp_matchmaking_queue%ROWTYPE;
BEGIN
    SELECT * INTO v_row
    FROM public.pvp_matchmaking_queue
    WHERE owner_id = p_owner_id
      AND status = 'searching'
      AND (p_queue_id IS NULL OR id = p_queue_id)
    ORDER BY joined_at DESC
    LIMIT 1
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', true, 'already', true);
    END IF;

    UPDATE public.pvp_matchmaking_queue
    SET status = 'cancelled', cancelled_at = NOW(), updated_at = NOW()
    WHERE id = v_row.id;

    UPDATE public.players
    SET pvp_requeue_available_at = NOW() + INTERVAL '15 seconds'
    WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object('ok', true, 'queue_id', v_row.id, 'status', 'cancelled');
END;
$$;

-- Skeleton matcher: same guild, SKIP LOCKED, sorted dual locks, create pvp run.
-- Full widening / pair caps completed in US4 tasks.
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
BEGIN
    PERFORM public.expire_pvp_queue_rows();

    IF NOT public._pvp_flag_on() THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'disabled');
    END IF;

    -- Pick oldest searching row (optionally guild-scoped)
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

    SELECT * INTO v_b
    FROM public.pvp_matchmaking_queue
    WHERE status = 'searching'
      AND expires_at >= NOW()
      AND guild_id = v_a.guild_id
      AND owner_id <> v_a.owner_id
      AND id <> v_a.id
      AND ABS(global_lp - v_a.global_lp) <= public.get_game_config_int('pvp_max_lp_range', 500)
      AND ABS(xi_rating - v_a.xi_rating) <= public.get_game_config_numeric('pvp_max_ovr_range', 12)
      AND NOT EXISTS (
          SELECT 1 FROM public.pvp_blocks blk
          WHERE (blk.blocker_id = v_a.owner_id AND blk.blocked_id = owner_id)
             OR (blk.blocker_id = owner_id AND blk.blocked_id = v_a.owner_id)
      )
    ORDER BY joined_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('matched', false, 'reason', 'no_partner', 'queue_id', v_a.id);
    END IF;

    -- Mark matching
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

GRANT EXECUTE ON FUNCTION public.expire_pvp_queue_rows() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.join_pvp_queue(BIGINT, BIGINT, BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.cancel_pvp_queue(BIGINT, UUID) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.try_match_pvp_queue(BIGINT) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 7) Schema guard
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('table:public.pvp_matchmaking_queue'),
            ('table:public.manager_rivalries'),
            ('table:public.pvp_blocks'),
            ('column:public.match_history.opponent_owner_id'),
            ('column:public.match_history.match_type'),
            ('column:public.match_history.global_lp_delta'),
            ('column:public.match_history.rivalry_counted'),
            ('column:public.players.pvp_badge_keys'),
            ('column:public.players.pvp_requeue_available_at'),
            ('function:public.join_pvp_queue'),
            ('function:public.cancel_pvp_queue'),
            ('function:public.try_match_pvp_queue'),
            ('function:public.expire_pvp_queue_rows'),
            ('policy:public.pvp_matchmaking_queue.pvp_queue_select'),
            ('policy:public.manager_rivalries.manager_rivalries_select'),
            ('policy:public.pvp_blocks.pvp_blocks_select')
    ) AS req(obj)
    WHERE
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NULL)
        OR (
            req.obj LIKE 'column:%'
            AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns c
                WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND c.column_name = split_part(req.obj, '.', 3)
            )
        )
        OR (
            req.obj LIKE 'function:%'
            AND to_regprocedure(
                CASE split_part(req.obj, ':', 2)
                    WHEN 'public.join_pvp_queue' THEN 'public.join_pvp_queue(bigint,bigint,bigint)'
                    WHEN 'public.cancel_pvp_queue' THEN 'public.cancel_pvp_queue(bigint,uuid)'
                    WHEN 'public.try_match_pvp_queue' THEN 'public.try_match_pvp_queue(bigint)'
                    WHEN 'public.expire_pvp_queue_rows' THEN 'public.expire_pvp_queue_rows()'
                    ELSE split_part(req.obj, ':', 2) || '()'
                END
            ) IS NULL
        )
        OR (
            req.obj LIKE 'policy:%'
            AND NOT EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 098 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

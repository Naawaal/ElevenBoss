-- 108_shelve_pvp_and_version_changelog.sql
-- Feature 056: Drop shelved PvP schema (098–106 era), restore pre-PvP lock CHECKs,
-- and redefine changelog claim identity as version-only (not version:commit).

BEGIN;

-- ---------------------------------------------------------------------------
-- 0) Clear in-flight PvP/practice runs so CHECK restores succeed
-- ---------------------------------------------------------------------------
DELETE FROM public.match_events
WHERE run_id IN (
    SELECT run_id FROM public.match_runs WHERE run_type IN ('pvp', 'practice')
);

DELETE FROM public.match_runs WHERE run_type IN ('pvp', 'practice');

DELETE FROM public.match_locks WHERE lock_type IN ('pvp', 'practice');

-- ---------------------------------------------------------------------------
-- 1) Drop PvP RPCs (all known overloads)
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public._pvp_flag_on() CASCADE;
DROP FUNCTION IF EXISTS public.expire_pvp_queue_rows() CASCADE;
DROP FUNCTION IF EXISTS public.join_pvp_queue(bigint, bigint, bigint) CASCADE;
DROP FUNCTION IF EXISTS public.cancel_pvp_queue(bigint, uuid) CASCADE;
DROP FUNCTION IF EXISTS public.try_match_pvp_queue(bigint) CASCADE;
DROP FUNCTION IF EXISTS public._pvp_search_bands(integer, numeric) CASCADE;
DROP FUNCTION IF EXISTS public.get_battle_hub_state(bigint, bigint) CASCADE;
DROP FUNCTION IF EXISTS public.finalize_pvp_match(uuid, integer, integer, numeric, numeric) CASCADE;
DROP FUNCTION IF EXISTS public.finalize_ai_practice_match(uuid, bigint, text, integer, integer, numeric, numeric, boolean) CASCADE;
DROP FUNCTION IF EXISTS public.reclaim_stale_pvp_matching(integer) CASCADE;
DROP FUNCTION IF EXISTS public.set_pvp_block(bigint, bigint, boolean) CASCADE;
DROP FUNCTION IF EXISTS public.set_pvp_prefs(bigint, boolean, boolean, boolean) CASCADE;
DROP FUNCTION IF EXISTS public.managers_pvp_blocked(bigint, bigint) CASCADE;
DROP FUNCTION IF EXISTS public._upsert_rivalry_from_pvp(bigint, bigint, boolean) CASCADE;
DROP FUNCTION IF EXISTS public.get_manager_rivalries(bigint) CASCADE;
DROP FUNCTION IF EXISTS public.get_rivalry_detail(bigint, bigint) CASCADE;
DROP FUNCTION IF EXISTS public.get_server_hottest_rivalries(bigint, integer) CASCADE;
DROP FUNCTION IF EXISTS public.pvp_division_rank(integer) CASCADE;
DROP FUNCTION IF EXISTS public.build_pvp_squad_snapshot(bigint) CASCADE;
DROP FUNCTION IF EXISTS public.apply_pvp_match_xp_once(uuid, uuid, bigint, text, jsonb, numeric) CASCADE;
DROP FUNCTION IF EXISTS public.apply_pvp_post_match_fitness_once(uuid, uuid, bigint, jsonb, uuid[], jsonb) CASCADE;
DROP FUNCTION IF EXISTS public.complete_pvp_run(uuid) CASCADE;
DROP FUNCTION IF EXISTS public.refresh_pvp_ghost_snapshot(bigint, uuid) CASCADE;
DROP FUNCTION IF EXISTS public.build_calibrated_pvp_ai_snapshot(bigint, numeric, integer) CASCADE;
DROP FUNCTION IF EXISTS public.bootstrap_pvp_ghost_snapshots() CASCADE;
DROP FUNCTION IF EXISTS public.refresh_all_pvp_ghost_snapshots(integer) CASCADE;
DROP FUNCTION IF EXISTS public.pvp_daily_ghost_refresh() CASCADE;

-- ---------------------------------------------------------------------------
-- 2) Drop PvP tables
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS public.pvp_ghost_encounters CASCADE;
DROP TABLE IF EXISTS public.pvp_ghost_snapshots CASCADE;
DROP TABLE IF EXISTS public.pvp_matchmaking_queue CASCADE;
DROP TABLE IF EXISTS public.manager_rivalries CASCADE;
DROP TABLE IF EXISTS public.pvp_blocks CASCADE;

-- ---------------------------------------------------------------------------
-- 3) Drop PvP columns on shared tables
-- ---------------------------------------------------------------------------
ALTER TABLE public.players
    DROP COLUMN IF EXISTS pvp_rivalry_dms,
    DROP COLUMN IF EXISTS pvp_rivalry_callouts,
    DROP COLUMN IF EXISTS pvp_rivalry_lb_visible,
    DROP COLUMN IF EXISTS pvp_badge_keys,
    DROP COLUMN IF EXISTS pvp_requeue_available_at,
    DROP COLUMN IF EXISTS pvp_ranked_matches;

ALTER TABLE public.match_history
    DROP CONSTRAINT IF EXISTS match_history_match_type_check,
    DROP CONSTRAINT IF EXISTS match_history_lp_mode_guard;

ALTER TABLE public.match_history
    DROP COLUMN IF EXISTS opponent_owner_id,
    DROP COLUMN IF EXISTS match_type,
    DROP COLUMN IF EXISTS global_lp_delta,
    DROP COLUMN IF EXISTS rivalry_counted,
    DROP COLUMN IF EXISTS opponent_mode,
    DROP COLUMN IF EXISTS opponent_snapshot_age_seconds;

ALTER TABLE public.match_runs
    DROP COLUMN IF EXISTS opponent_mode;

-- ---------------------------------------------------------------------------
-- 4) Delete PvP game_config keys
-- ---------------------------------------------------------------------------
DELETE FROM public.game_config
WHERE key IN (
    'battle_pvp_enabled',
    'pvp_rewards_enabled',
    'pvp_rivalries_enabled',
    'pvp_rivalry_dms_enabled',
    'pvp_server_leaderboard_enabled',
    'ai_practice_rewards_enabled',
    'pvp_search_timeout_seconds',
    'pvp_matchmaker_interval_seconds',
    'pvp_energy_cost',
    'pvp_rewarded_matches_daily',
    'pvp_same_pair_cooldown_minutes',
    'pvp_same_pair_matches_daily',
    'pvp_initial_lp_range',
    'pvp_initial_ovr_range',
    'pvp_max_lp_range',
    'pvp_max_ovr_range',
    'pvp_provisional_matches',
    'pvp_coin_multiplier_win',
    'pvp_coin_multiplier_draw',
    'pvp_coin_multiplier_loss',
    'ai_practice_energy_cost',
    'ai_practice_new_manager_reward_multiplier',
    'ai_practice_established_reward_multiplier',
    'ai_practice_rewarded_daily',
    'pvp_rivalry_activation_matches',
    'pvp_rivalry_activation_days',
    'pvp_rivalry_dormant_days',
    'match_engine_v3_pvp',
    'match_engine_v3_practice',
    'match_energy_pvp',
    'match_energy_practice',
    'pvp_backfill_enabled',
    'pvp_backfill_daily_limit'
);

-- ---------------------------------------------------------------------------
-- 5) Restore pre-PvP CHECK constraints + acquire_match_lock (047 body)
-- ---------------------------------------------------------------------------
ALTER TABLE public.match_runs DROP CONSTRAINT IF EXISTS match_runs_run_type_check;
ALTER TABLE public.match_runs
    ADD CONSTRAINT match_runs_run_type_check
    CHECK (run_type IN ('bot', 'friendly', 'league'));

ALTER TABLE public.match_locks DROP CONSTRAINT IF EXISTS match_locks_lock_type_check;
ALTER TABLE public.match_locks
    ADD CONSTRAINT match_locks_lock_type_check
    CHECK (lock_type IN ('friendly', 'league', 'bot'));

CREATE OR REPLACE FUNCTION public.acquire_match_lock(
    p_discord_id BIGINT,
    p_lock_type TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_inserted BIGINT;
BEGIN
    IF p_lock_type NOT IN ('friendly', 'league', 'bot') THEN
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
-- 6) Changelog: normalize stored key + version-only claim semantics
-- ---------------------------------------------------------------------------
UPDATE public.game_config
SET value_json = jsonb_set(
    value_json,
    '{deployment_key}',
    to_jsonb(
        COALESCE(
            NULLIF(value_json #>> '{version}', ''),
            split_part(COALESCE(value_json #>> '{deployment_key}', ''), ':', 1)
        )
    )
)
WHERE key = 'last_changelog_deployment'
  AND value_json IS NOT NULL;

CREATE OR REPLACE FUNCTION public.claim_deployment_changelog(
    p_deployment_key TEXT,
    p_instance_id TEXT DEFAULT 'default'
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_rec JSONB;
    v_curr_key TEXT;
    v_curr_version TEXT;
    v_claimed_at TIMESTAMPTZ;
    v_same BOOLEAN;
BEGIN
    -- p_deployment_key MUST be the changelog version string only (e.g. '2.1.0').
    SELECT value_json INTO v_rec
    FROM public.game_config
    WHERE key = 'last_changelog_deployment'
    FOR UPDATE;

    IF v_rec IS NOT NULL THEN
        v_curr_key := v_rec #>> '{deployment_key}';
        v_curr_version := COALESCE(
            NULLIF(v_rec #>> '{version}', ''),
            split_part(COALESCE(v_curr_key, ''), ':', 1)
        );
        v_claimed_at := (v_rec #>> '{claimed_at}')::TIMESTAMPTZ;
        v_same := (
            v_curr_key = p_deployment_key
            OR v_curr_version = p_deployment_key
            OR split_part(COALESCE(v_curr_key, ''), ':', 1) = p_deployment_key
        );

        IF v_same AND (v_rec #>> '{posted_at}') IS NOT NULL THEN
            RETURN jsonb_build_object('status', 'already_posted', 'deployment_key', p_deployment_key);
        END IF;

        IF v_same AND v_claimed_at IS NOT NULL AND v_claimed_at > NOW() - INTERVAL '10 minutes' THEN
            RETURN jsonb_build_object('status', 'already_claimed', 'deployment_key', p_deployment_key);
        END IF;
    END IF;

    INSERT INTO public.game_config (key, value_json)
    VALUES (
        'last_changelog_deployment',
        jsonb_build_object(
            'deployment_key', p_deployment_key,
            'version', p_deployment_key,
            'claimed_at', NOW(),
            'instance_id', p_instance_id
        )
    )
    ON CONFLICT (key) DO UPDATE
    SET value_json = EXCLUDED.value_json;

    RETURN jsonb_build_object('status', 'claimed', 'deployment_key', p_deployment_key);
END;
$$;

GRANT EXECUTE ON FUNCTION public.claim_deployment_changelog(TEXT, TEXT) TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.complete_deployment_changelog(
    p_deployment_key TEXT,
    p_version TEXT,
    p_commit TEXT,
    p_channel_id BIGINT
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    -- Identity remains p_deployment_key / p_version (same string). p_commit is ops metadata only.
    UPDATE public.game_config
    SET value_json = jsonb_build_object(
        'deployment_key', p_deployment_key,
        'version', COALESCE(NULLIF(p_version, ''), p_deployment_key),
        'commit', p_commit,
        'posted_at', NOW(),
        'channel_id', p_channel_id
    )
    WHERE key = 'last_changelog_deployment';

    RETURN jsonb_build_object('status', 'completed', 'deployment_key', p_deployment_key);
END;
$$;

GRANT EXECUTE ON FUNCTION public.complete_deployment_changelog(TEXT, TEXT, TEXT, BIGINT) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 7) Schema guard — automation required; PvP must be gone
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    req TEXT;
    reqs TEXT[] := ARRAY[
        'table:public.topgg_vote_reminders',
        'function:public.claim_due_topgg_vote_reminders',
        'function:public.claim_deployment_changelog',
        'function:public.complete_deployment_changelog'
    ];
    gone TEXT;
    gone_objs TEXT[] := ARRAY[
        'table:public.pvp_matchmaking_queue',
        'table:public.manager_rivalries',
        'table:public.pvp_blocks',
        'table:public.pvp_ghost_snapshots',
        'table:public.pvp_ghost_encounters',
        'function:public.join_pvp_queue',
        'function:public.try_match_pvp_queue',
        'function:public.finalize_pvp_match',
        'function:public.complete_pvp_run',
        'function:public.get_battle_hub_state'
    ];
BEGIN
    FOREACH req IN ARRAY reqs LOOP
        IF split_part(req, ':', 1) = 'table' THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = split_part(split_part(req, ':', 2), '.', 1)
                  AND table_name = split_part(split_part(req, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION '108 guard missing %', req;
            END IF;
        ELSIF split_part(req, ':', 1) = 'function' THEN
            IF to_regprocedure(split_part(req, ':', 2) || (
                CASE split_part(split_part(req, ':', 2), '.', 2)
                    WHEN 'claim_due_topgg_vote_reminders' THEN '(integer)'
                    WHEN 'claim_deployment_changelog' THEN '(text,text)'
                    WHEN 'complete_deployment_changelog' THEN '(text,text,text,bigint)'
                    ELSE ''
                END
            )) IS NULL THEN
                RAISE EXCEPTION '108 guard missing %', req;
            END IF;
        END IF;
    END LOOP;

    FOREACH gone IN ARRAY gone_objs LOOP
        IF split_part(gone, ':', 1) = 'table' THEN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = split_part(split_part(gone, ':', 2), '.', 1)
                  AND table_name = split_part(split_part(gone, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION '108 guard: PvP object still present %', gone;
            END IF;
        ELSIF split_part(gone, ':', 1) = 'function' THEN
            IF EXISTS (
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = split_part(split_part(gone, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION '108 guard: PvP function still present %', gone;
            END IF;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM public.game_config
        WHERE key IN ('battle_pvp_enabled', 'pvp_rewards_enabled', 'pvp_rivalries_enabled')
    ) THEN
        RAISE EXCEPTION '108 guard: PvP game_config flags still present';
    END IF;
END;
$$;

COMMIT;

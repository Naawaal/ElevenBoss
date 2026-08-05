-- supabase/migrations/105_fix_complete_pvp_run_ghost_ai.sql
-- BUG-2 fix: complete_pvp_run always returned missing_history_rows for ghost/AI matches
-- because away_discord_id is NULL (ai_backfill) or has no match_history row (ghost).
-- Also fixes the ghost snapshot stale problem by adding a daily scheduler hook.

-- Replace complete_pvp_run to skip away-side checks for non-live opponent modes.
DROP FUNCTION IF EXISTS public.complete_pvp_run(UUID);
CREATE OR REPLACE FUNCTION public.complete_pvp_run(
    p_run_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run       public.match_runs%ROWTYPE;
    v_policy    JSONB;
    v_xp_req    BOOLEAN;
    v_fit_req   BOOLEAN;
    v_opp_mode  TEXT;
    v_home_hist public.match_history%ROWTYPE;
    v_away_hist public.match_history%ROWTYPE;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND OR v_run.run_type <> 'pvp' OR v_run.status <> 'completing' THEN
        RAISE EXCEPTION 'Invalid match run % for completion', p_run_id;
    END IF;

    v_opp_mode := COALESCE(v_run.opponent_mode, 'live');
    v_policy   := COALESCE(v_run.squad_snapshot -> 'finalization_policy', '{}'::jsonb);
    v_xp_req   := COALESCE((v_policy #>> '{xp_enabled}')::BOOLEAN,      FALSE);
    v_fit_req  := COALESCE((v_policy #>> '{fitness_enabled}')::BOOLEAN,  FALSE);

    -- Home history row is always required
    SELECT * INTO v_home_hist
    FROM public.match_history
    WHERE run_id = p_run_id AND player_id = v_run.home_discord_id AND match_type = 'pvp';

    IF v_home_hist.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'missing_home_history');
    END IF;

    IF v_xp_req AND v_home_hist.xp_applied_at IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'missing_home_xp_stamp');
    END IF;

    IF v_fit_req AND v_home_hist.fatigue_applied_at IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'missing_home_fatigue_stamp');
    END IF;

    -- Away history only required for live human matches
    IF v_opp_mode = 'live' AND v_run.away_discord_id IS NOT NULL THEN
        SELECT * INTO v_away_hist
        FROM public.match_history
        WHERE run_id = p_run_id AND player_id = v_run.away_discord_id AND match_type = 'pvp';

        IF v_away_hist.id IS NULL THEN
            RETURN jsonb_build_object('ok', false, 'reason', 'missing_away_history');
        END IF;

        IF v_xp_req AND v_away_hist.xp_applied_at IS NULL THEN
            RETURN jsonb_build_object('ok', false, 'reason', 'missing_away_xp_stamp');
        END IF;

        IF v_fit_req AND v_away_hist.fatigue_applied_at IS NULL THEN
            RETURN jsonb_build_object('ok', false, 'reason', 'missing_away_fatigue_stamp');
        END IF;
    END IF;

    UPDATE public.match_runs
    SET status = 'completed', completed_at = NOW(), updated_at = NOW()
    WHERE id = p_run_id;

    -- Release locks: home always; away only for live (NULL-safe)
    PERFORM public.release_match_lock(v_run.home_discord_id);
    IF v_opp_mode = 'live' AND v_run.away_discord_id IS NOT NULL THEN
        PERFORM public.release_match_lock(v_run.away_discord_id);
    END IF;

    RETURN jsonb_build_object('ok', true, 'completed', true, 'opponent_mode', v_opp_mode);
END;
$$;

-- Restore service_role-only grant (same as migration 102)
REVOKE ALL ON FUNCTION public.complete_pvp_run(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_pvp_run(UUID) TO service_role;

-- BUG-3: add helper RPC for daily ghost snapshot refresh (callable from scheduler)
-- The Python scheduler job calls this via db.rpc("pvp_daily_ghost_refresh", {})
CREATE OR REPLACE FUNCTION public.pvp_daily_ghost_refresh()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN public.refresh_all_pvp_ghost_snapshots(24);
END;
$$;

GRANT EXECUTE ON FUNCTION public.pvp_daily_ghost_refresh() TO anon, authenticated, service_role;

-- ── Schema guard ──────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF to_regprocedure('public.complete_pvp_run(uuid)') IS NULL THEN
        RAISE EXCEPTION 'Migration 105: complete_pvp_run not found after replacement';
    END IF;
    IF to_regprocedure('public.pvp_daily_ghost_refresh()') IS NULL THEN
        RAISE EXCEPTION 'Migration 105: pvp_daily_ghost_refresh not found';
    END IF;
END $$;

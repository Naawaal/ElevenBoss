-- 091: Measured hot-path indexes (050 T029/T064; T036 waived)
-- Evidence: scratch/explain_snapshots/20260731T142205Z_050_*.txt
-- Rule: no index without EXPLAIN showing why (spec 050 / query-plan-gate).

-- ---------------------------------------------------------------------------
-- Global leaderboard window (get_global_leaderboard_page)
-- Before: Seq Scan on players + Sort (global_lp DESC, discord_id)
-- Snapshot: 20260731T142205Z_050_global_lb_window.txt
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_players_global_lp_human
    ON public.players (global_lp DESC, discord_id ASC)
    WHERE COALESCE(is_ai, false) = false;

-- ---------------------------------------------------------------------------
-- Division leaderboard window + rank (get_division_leaderboard_page)
-- Before: Index Scan idx_players_division then Sort (LP, GD, discord_id)
-- Snapshot: 20260731T142205Z_050_div_lb_rank_window.txt
-- Composite matches WINDOW / viewer-rank ordering so growing divisions avoid
-- full in-memory sorts after the division filter.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_players_division_lb_human
    ON public.players (division, league_points DESC, goal_difference DESC, discord_id ASC)
    WHERE COALESCE(is_ai, false) = false;

-- ---------------------------------------------------------------------------
-- League standings first-page / journal fill (fetch_standings → played fixtures)
-- Before: Bitmap Index season_id (all matchdays) then Filter is_played
--         removed 56/56 rows on sample season
-- Snapshot: 20260731T142205Z_050_standings_played_fixtures.txt
-- Symmetric to idx_league_fixtures_season_unplayed (080).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_league_fixtures_season_played
    ON public.league_fixtures (season_id)
    WHERE is_played = true;

-- ---------------------------------------------------------------------------
-- Market browse (T036): WAIVED — no new index
-- browse_active_*: Index Scan transfer_listings_status_expires_idx already;
-- Sort only over active non-expired rows (6 on sample). Revisit when active
-- listings are large enough that Sort dominates Execution Time.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF to_regclass('public.idx_players_global_lp_human') IS NULL THEN
        RAISE EXCEPTION '091 guard failed: idx_players_global_lp_human';
    END IF;
    IF to_regclass('public.idx_players_division_lb_human') IS NULL THEN
        RAISE EXCEPTION '091 guard failed: idx_players_division_lb_human';
    END IF;
    IF to_regclass('public.idx_league_fixtures_season_played') IS NULL THEN
        RAISE EXCEPTION '091 guard failed: idx_league_fixtures_season_played';
    END IF;
END $$;

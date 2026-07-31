-- 092: Prefer division LB composite (follow-up to 091 measured indexes)
-- After 091, EXPLAIN still chose idx_players_division then Sort for the division
-- window (20260731T142345Z_050_div_lb_rank_window.txt / forced_index_use.txt).
-- Leftmost prefix of idx_players_division_lb_human covers equality on division;
-- dropping the bare index lets the planner use ordered scans for LB windows.

DROP INDEX IF EXISTS public.idx_players_division;

DO $$
BEGIN
    IF to_regclass('public.idx_players_division_lb_human') IS NULL THEN
        RAISE EXCEPTION '092 guard failed: idx_players_division_lb_human missing (apply 091 first)';
    END IF;
    IF to_regclass('public.idx_players_division') IS NOT NULL THEN
        RAISE EXCEPTION '092 guard failed: idx_players_division still present';
    END IF;
END $$;

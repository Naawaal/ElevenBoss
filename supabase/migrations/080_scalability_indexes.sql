-- US-43 Phase 1: measured scalability indexes
-- Justified by hub/league query patterns (season_id + matchday / club ledger scans).
-- EXPLAIN snapshots: scratch/explain_snapshots/ + contracts/query-plan-gate.md

CREATE INDEX IF NOT EXISTS idx_league_fixtures_season_matchday
    ON public.league_fixtures (season_id, matchday);

CREATE INDEX IF NOT EXISTS idx_league_fixtures_season_unplayed
    ON public.league_fixtures (season_id)
    WHERE is_played = false;

CREATE INDEX IF NOT EXISTS idx_economy_ledger_club_created
    ON public.economy_ledger (club_id, created_at DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'idx_league_fixtures_season_matchday'
  ) THEN
    RAISE EXCEPTION '080 guard failed: idx_league_fixtures_season_matchday missing';
  END IF;
END $$;

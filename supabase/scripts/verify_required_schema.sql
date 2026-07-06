-- Run after migrations: psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql
-- Exits non-zero (via RAISE) if required ElevenBoss objects are missing.

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
  SELECT array_agg(req.obj ORDER BY req.obj)
  INTO v_missing
  FROM (
    VALUES
      ('table:public.players'),
      ('table:public.player_cards'),
      ('table:public.active_evolutions'),
      ('table:public.active_training'),
      ('table:public.economy_ledger'),
      ('table:public.league_members'),
      ('table:public.match_locks'),
      ('table:public.match_runs'),
      ('column:public.players.training_energy'),
      ('column:public.players.daily_drill_count'),
      ('column:public.players.daily_drill_reset_at'),
      ('column:public.players.last_evolution_started_at'),
      ('function:public.process_stat_drill'),
      ('function:public.sync_training_energy'),
      ('function:public.get_evolution_hub_status')
  ) AS req(obj)
  WHERE NOT (
    (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
    OR (
      req.obj LIKE 'column:%'
      AND EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
          AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
          AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
      )
    )
    OR (
      req.obj LIKE 'function:%'
      AND CASE split_part(req.obj, ':', 3)
        WHEN 'process_stat_drill' THEN to_regprocedure('public.process_stat_drill(bigint,uuid,text)')
        WHEN 'sync_training_energy' THEN to_regprocedure('public.sync_training_energy(bigint)')
        WHEN 'get_evolution_hub_status' THEN to_regprocedure('public.get_evolution_hub_status(bigint)')
        ELSE NULL
      END IS NOT NULL
    )
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema verify failed — missing: %', array_to_string(v_missing, ', ');
  END IF;

  RAISE NOTICE 'Schema verify OK';
END $$;

-- 071: backfill league_members.registered_at when 015 CREATE TABLE IF NOT EXISTS
-- was a no-op on an older league_members shape (Dynamics start selected this column).

ALTER TABLE public.league_members
    ADD COLUMN IF NOT EXISTS registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

DO $$
DECLARE
    missing text;
BEGIN
    SELECT string_agg(req.obj, ', ' ORDER BY req.obj)
      INTO missing
    FROM (VALUES
            ('column:public.league_members.registered_at')
         ) AS req(obj)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
          AND c.table_name   = split_part(split_part(req.obj, ':', 2), '.', 2)
          AND c.column_name  = split_part(split_part(req.obj, ':', 2), '.', 3)
    );
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'migration 071 schema guard failed — missing: %', missing;
    END IF;
END $$;

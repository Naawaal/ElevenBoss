-- US-28: Per-season dual thread IDs for league announcements

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS announcement_message_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS journal_thread_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS matchday_thread_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS journal_standings_message_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS thread_format TEXT NOT NULL DEFAULT 'legacy';

ALTER TABLE public.league_seasons DROP CONSTRAINT IF EXISTS league_seasons_thread_format_check;
ALTER TABLE public.league_seasons
    ADD CONSTRAINT league_seasons_thread_format_check
    CHECK (thread_format IN ('legacy', 'dual_v2'));

-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.league_seasons.announcement_message_id'),
            ('column:public.league_seasons.journal_thread_id'),
            ('column:public.league_seasons.matchday_thread_id'),
            ('column:public.league_seasons.journal_standings_message_id'),
            ('column:public.league_seasons.thread_format')
    ) AS req(obj)
    WHERE NOT EXISTS (
        SELECT 1 FROM (
            SELECT 'column:' || table_schema || '.' || table_name || '.' || column_name AS obj
            FROM information_schema.columns WHERE table_schema = 'public'
        ) existing WHERE existing.obj = req.obj
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

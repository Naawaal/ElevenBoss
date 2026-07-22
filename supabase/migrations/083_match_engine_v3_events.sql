-- NSS v3: durable match_events + match_runs version pins (041-match-engine-v3 Phase 0)

ALTER TABLE public.match_runs
    ADD COLUMN IF NOT EXISTS engine_version TEXT NOT NULL DEFAULT 'nss_v2';

ALTER TABLE public.match_runs
    ADD COLUMN IF NOT EXISTS simulation_schema_version INT NOT NULL DEFAULT 1;

ALTER TABLE public.match_runs
    ADD COLUMN IF NOT EXISTS event_schema_version INT NOT NULL DEFAULT 1;

ALTER TABLE public.match_runs
    ADD COLUMN IF NOT EXISTS events_flushed_thru INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS public.match_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES public.match_runs(id) ON DELETE CASCADE,
    seq             INT NOT NULL CHECK (seq > 0),
    schema_version  INT NOT NULL DEFAULT 1,
    engine_version  TEXT NOT NULL,
    minute          INT NOT NULL CHECK (minute >= 0 AND minute <= 120),
    event_type      TEXT NOT NULL,
    side            TEXT NULL CHECK (side IS NULL OR side IN ('home', 'away', 'neutral')),
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    causal_hint     TEXT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_match_events_run_type
    ON public.match_events (run_id, event_type);

ALTER TABLE public.match_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS match_events_select ON public.match_events;
DROP POLICY IF EXISTS match_events_insert ON public.match_events;

CREATE POLICY match_events_select ON public.match_events
    FOR SELECT
    TO anon, authenticated, service_role
    USING (true);

CREATE POLICY match_events_insert ON public.match_events
    FOR INSERT
    TO anon, authenticated, service_role
    WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE public.match_events TO anon, authenticated, service_role;

-- Dual-run feature flags (ops-tunable)
INSERT INTO public.game_config (key, value_json) VALUES
    ('match_engine_v3_bot', '0'::jsonb),
    ('match_engine_v3_league', '0'::jsonb),
    ('match_engine_v3_friendly', '0'::jsonb)
ON CONFLICT (key) DO NOTHING;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('table:public.match_events'),
            ('column:public.match_runs.engine_version'),
            ('column:public.match_runs.simulation_schema_version'),
            ('column:public.match_runs.event_schema_version'),
            ('column:public.match_runs.events_flushed_thru'),
            ('policy:public.match_events.match_events_select'),
            ('policy:public.match_events.match_events_insert')
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
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1
                FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 083 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

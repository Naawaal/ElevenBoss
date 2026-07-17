-- 065: League Automation (flags, guild opt-in, Monday reopen cooldown)
-- Spec: specs/021-league-automation-and-config/

ALTER TABLE public.guild_config
    ADD COLUMN IF NOT EXISTS league_automation_enabled BOOLEAN NULL;

ALTER TABLE public.guild_config
    ADD COLUMN IF NOT EXISTS next_auto_registration_at TIMESTAMPTZ NULL;

ALTER TABLE public.guild_config
    ADD COLUMN IF NOT EXISTS automation_last_error TEXT NULL;

INSERT INTO public.game_config (key, value_json) VALUES
    ('league_automation_enabled', 'false'),
    ('league_automation_registration_hours', '48')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.league_automation_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('league_automation_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

GRANT EXECUTE ON FUNCTION public.league_automation_enabled() TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.guild_config.league_automation_enabled'),
            ('column:public.guild_config.next_auto_registration_at'),
            ('column:public.guild_config.automation_last_error'),
            ('function:league_automation_enabled')
    ) AS req(obj)
    WHERE NOT (
        (
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
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'league_automation_enabled'
                    THEN to_regprocedure('public.league_automation_enabled()')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '065 schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

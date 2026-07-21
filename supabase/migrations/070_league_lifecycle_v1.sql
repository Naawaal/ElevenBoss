-- 070: League Lifecycle Rulebook V1
-- Spec: specs/026-league-lifecycle-rulebook/

-- ---------------------------------------------------------------------------
-- guild_config: timezone, resolution hour, cutover flag
-- ---------------------------------------------------------------------------

ALTER TABLE public.guild_config
    ADD COLUMN IF NOT EXISTS league_timezone TEXT NULL;

ALTER TABLE public.guild_config
    ADD COLUMN IF NOT EXISTS league_resolution_hour_local SMALLINT NULL;

ALTER TABLE public.guild_config
    ADD COLUMN IF NOT EXISTS league_lifecycle_v1_enabled BOOLEAN NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'guild_config_league_resolution_hour_check'
    ) THEN
        ALTER TABLE public.guild_config
            ADD CONSTRAINT guild_config_league_resolution_hour_check
            CHECK (
                league_resolution_hour_local IS NULL
                OR (league_resolution_hour_local >= 0 AND league_resolution_hour_local <= 23)
            );
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- league_members: membership fields
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_members
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE public.league_members
    ADD COLUMN IF NOT EXISTS auto_register BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.league_members
    ADD COLUMN IF NOT EXISTS inactivity_count INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- league_seasons: V1 statuses + frozen schedule / ruleset
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS ruleset_version TEXT NULL;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS engine_version TEXT NULL;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS ruleset_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS timezone TEXT NULL;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS resolution_hour_local SMALLINT NULL;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS phase_deadlines JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS pause_started_at TIMESTAMPTZ NULL;

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS total_paused_seconds BIGINT NOT NULL DEFAULT 0;

ALTER TABLE public.league_seasons DROP CONSTRAINT IF EXISTS league_seasons_status_check;
ALTER TABLE public.league_seasons
    ADD CONSTRAINT league_seasons_status_check
    CHECK (status IN (
        'dormant',
        'registration',
        'registration_open',
        'registration_locked',
        'preparing',
        'active',
        'paused',
        'settling',
        'completed',
        'cancelled',
        'failed'
    ));

ALTER TABLE public.league_seasons DROP CONSTRAINT IF EXISTS league_seasons_pacing_mode_check;
ALTER TABLE public.league_seasons
    ADD CONSTRAINT league_seasons_pacing_mode_check
    CHECK (pacing_mode IN ('legacy', 'dynamics', 'lifecycle_v1'));

-- ---------------------------------------------------------------------------
-- league_registrations
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'registered'
        CHECK (status IN ('registered', 'withdrawn', 'rejected', 'locked')),
    eligibility_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    deposit_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (deposit_status IN ('pending', 'charged', 'refunded', 'waived')),
    deposit_amount BIGINT NOT NULL DEFAULT 0,
    UNIQUE (season_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_league_registrations_season
    ON public.league_registrations(season_id);

-- ---------------------------------------------------------------------------
-- league_divisions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_divisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    tier INTEGER NOT NULL CHECK (tier >= 1),
    bot_rating_snapshot NUMERIC NULL,
    UNIQUE (season_id, tier)
);

-- ---------------------------------------------------------------------------
-- league_participants extensions
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_participants
    ADD COLUMN IF NOT EXISTS division_id UUID NULL REFERENCES public.league_divisions(id) ON DELETE SET NULL;

ALTER TABLE public.league_participants
    ADD COLUMN IF NOT EXISTS participant_type TEXT NULL;

ALTER TABLE public.league_participants
    ADD COLUMN IF NOT EXISTS seed INTEGER NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'league_participants_participant_type_check'
    ) THEN
        ALTER TABLE public.league_participants
            ADD CONSTRAINT league_participants_participant_type_check
            CHECK (participant_type IS NULL OR participant_type IN ('human', 'bot'));
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- league_matchdays
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_matchdays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    matchday_number INTEGER NOT NULL CHECK (matchday_number >= 1),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN (
            'scheduled', 'open', 'closing_soon', 'locked',
            'resolving', 'completed', 'resolution_failed'
        )),
    reminder_sent_at TIMESTAMPTZ NULL,
    UNIQUE (season_id, matchday_number)
);

CREATE INDEX IF NOT EXISTS idx_league_matchdays_season_status
    ON public.league_matchdays(season_id, status);

-- ---------------------------------------------------------------------------
-- league_fixtures extensions
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS matchday_id UUID NULL REFERENCES public.league_matchdays(id) ON DELETE SET NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS status TEXT NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS result_type TEXT NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS match_seed TEXT NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS engine_version TEXT NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS ruleset_version TEXT NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS squad_snapshot_home JSONB NULL;

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS squad_snapshot_away JSONB NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'league_fixtures_status_check'
    ) THEN
        ALTER TABLE public.league_fixtures
            ADD CONSTRAINT league_fixtures_status_check
            CHECK (
                status IS NULL OR status IN (
                    'scheduled', 'available', 'running', 'settling',
                    'settled', 'forfeit', 'void', 'failed_retryable'
                )
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'league_fixtures_result_type_check'
    ) THEN
        ALTER TABLE public.league_fixtures
            ADD CONSTRAINT league_fixtures_result_type_check
            CHECK (
                result_type IS NULL OR result_type IN (
                    'settled', 'forfeit', 'double_forfeit', 'void'
                )
            );
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- league_final_standings
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_final_standings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    division_id UUID NULL REFERENCES public.league_divisions(id) ON DELETE SET NULL,
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    played INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 0,
    drawn INTEGER NOT NULL DEFAULT 0,
    lost INTEGER NOT NULL DEFAULT 0,
    gf INTEGER NOT NULL DEFAULT 0,
    ga INTEGER NOT NULL DEFAULT 0,
    gd INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    movement TEXT NOT NULL DEFAULT 'none'
        CHECK (movement IN ('champion', 'promoted', 'stayed', 'relegated', 'none')),
    participant_type TEXT NOT NULL DEFAULT 'human'
        CHECK (participant_type IN ('human', 'bot')),
    UNIQUE (season_id, player_id)
);

-- ---------------------------------------------------------------------------
-- journal / ops / outbox
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_transition_journal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NULL REFERENCES public.league_seasons(id) ON DELETE SET NULL,
    transition TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    trigger TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ruleset_version TEXT NOT NULL DEFAULT 'lifecycle-v1',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_league_transition_journal_season
    ON public.league_transition_journal(season_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS public.league_operation_runs (
    operation_key TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'started'
        CHECK (status IN ('started', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ NULL,
    error TEXT NULL,
    worker_id TEXT NULL
);

CREATE TABLE IF NOT EXISTS public.league_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ NULL,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_league_outbox_pending
    ON public.league_outbox(created_at)
    WHERE published_at IS NULL;

-- ---------------------------------------------------------------------------
-- game_config
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('league_lifecycle_v1_enabled', 'false'),
    ('league_lifecycle_min_humans', '4'),
    ('league_lifecycle_registration_hours', '48'),
    ('league_lifecycle_preparation_hours', '24'),
    ('league_lifecycle_settlement_hours', '24'),
    ('league_lifecycle_offseason_hours', '72'),
    ('league_lifecycle_default_resolution_hour', '0'),
    ('league_lifecycle_promo_min_eligible_matches', '7'),
    ('league_lifecycle_wake_minutes', '5')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.league_lifecycle_v1_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('league_lifecycle_v1_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

GRANT EXECUTE ON FUNCTION public.league_lifecycle_v1_enabled() TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_divisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_matchdays ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_final_standings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_transition_journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_operation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_outbox ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'league_registrations',
        'league_divisions',
        'league_matchdays',
        'league_final_standings',
        'league_transition_journal',
        'league_operation_runs',
        'league_outbox'
    ]
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            t || '_select', t
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO anon, authenticated, service_role USING (true)',
            t || '_select', t
        );
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            t || '_insert', t
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR INSERT TO anon, authenticated, service_role WITH CHECK (true)',
            t || '_insert', t
        );
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            t || '_update', t
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true)',
            t || '_update', t
        );
    END LOOP;
END $$;

GRANT ALL ON public.league_registrations TO anon, authenticated, service_role;
GRANT ALL ON public.league_divisions TO anon, authenticated, service_role;
GRANT ALL ON public.league_matchdays TO anon, authenticated, service_role;
GRANT ALL ON public.league_final_standings TO anon, authenticated, service_role;
GRANT ALL ON public.league_transition_journal TO anon, authenticated, service_role;
GRANT ALL ON public.league_operation_runs TO anon, authenticated, service_role;
GRANT ALL ON public.league_outbox TO anon, authenticated, service_role;

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
            ('column:public.guild_config.league_timezone'),
            ('column:public.guild_config.league_resolution_hour_local'),
            ('column:public.guild_config.league_lifecycle_v1_enabled'),
            ('column:public.league_seasons.ruleset_version'),
            ('column:public.league_seasons.timezone'),
            ('column:public.league_fixtures.result_type'),
            ('column:public.league_fixtures.matchday_id'),
            ('table:public.league_registrations'),
            ('table:public.league_divisions'),
            ('table:public.league_matchdays'),
            ('table:public.league_final_standings'),
            ('table:public.league_transition_journal'),
            ('table:public.league_operation_runs'),
            ('table:public.league_outbox'),
            ('function:league_lifecycle_v1_enabled')
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
            req.obj LIKE 'table:%'
            AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL
        )
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'league_lifecycle_v1_enabled'
                    THEN to_regprocedure('public.league_lifecycle_v1_enabled()')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '070 schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

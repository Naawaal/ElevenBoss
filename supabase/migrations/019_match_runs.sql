-- Durable match run tracking for restart recovery and fixture-level locking.

CREATE TABLE IF NOT EXISTS public.match_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type            TEXT NOT NULL CHECK (run_type IN ('bot', 'friendly', 'league')),
    status              TEXT NOT NULL DEFAULT 'streaming'
                        CHECK (status IN ('streaming', 'completing', 'completed', 'abandoned', 'failed')),
    home_discord_id     BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    away_discord_id     BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    active_discord_id   BIGINT,
    fixture_id          UUID REFERENCES public.league_fixtures(id) ON DELETE SET NULL,
    sim_seed            BIGINT NOT NULL,
    squad_snapshot      JSONB NOT NULL DEFAULT '{}',
    guild_id            BIGINT,
    thread_id           BIGINT,
    ticker_message_id   BIGINT,
    channel_id          BIGINT,
    last_minute         INT NOT NULL DEFAULT 0,
    home_score          INT NOT NULL DEFAULT 0,
    away_score          INT NOT NULL DEFAULT 0,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    completion_key      TEXT UNIQUE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_match_runs_active_fixture
    ON public.match_runs(fixture_id)
    WHERE fixture_id IS NOT NULL AND status IN ('streaming', 'completing');

CREATE INDEX IF NOT EXISTS idx_match_runs_status ON public.match_runs(status);

ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS fixture_id UUID REFERENCES public.league_fixtures(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_match_history_player_fixture
    ON public.match_history(player_id, fixture_id)
    WHERE fixture_id IS NOT NULL;

GRANT ALL PRIVILEGES ON TABLE public.match_runs TO anon, authenticated, service_role;

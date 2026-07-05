-- supabase/migrations/011_friendly_matches.sql

-- 1. Create match_locks table to enforce player concurrency locking
CREATE TABLE IF NOT EXISTS public.match_locks (
    discord_id BIGINT PRIMARY KEY REFERENCES public.players(discord_id) ON DELETE CASCADE,
    lock_type TEXT NOT NULL CHECK (lock_type IN ('friendly', 'league', 'bot')),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- 2. Create friendly_match_logs table for isolated friendly match history
CREATE TABLE IF NOT EXISTS public.friendly_match_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    home_discord_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    away_discord_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    box_score JSONB NOT NULL,
    key_events JSONB NOT NULL,
    played_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- 3. Grant table privileges
GRANT ALL PRIVILEGES ON TABLE public.match_locks TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.friendly_match_logs TO anon, authenticated, service_role;

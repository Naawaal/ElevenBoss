-- supabase/migrations/009_league_stats.sql

-- 1. Create match_logs table
CREATE TABLE IF NOT EXISTS public.match_logs (
    fixture_id UUID PRIMARY KEY REFERENCES public.league_fixtures(id) ON DELETE CASCADE,
    box_score JSONB NOT NULL,
    key_events JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- 2. Create player_season_stats table
CREATE TABLE IF NOT EXISTS public.player_season_stats (
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    goals INTEGER DEFAULT 0 NOT NULL,
    assists INTEGER DEFAULT 0 NOT NULL,
    clean_sheets INTEGER DEFAULT 0 NOT NULL,
    motm_awards INTEGER DEFAULT 0 NOT NULL,
    average_rating NUMERIC(4,2) DEFAULT 6.00 NOT NULL,
    matches_played INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (player_id, season_id)
);

-- 3. Create indexes for performance leaderboards
CREATE INDEX IF NOT EXISTS idx_player_season_stats_season_goals ON public.player_season_stats(season_id, goals DESC);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_season_assists ON public.player_season_stats(season_id, assists DESC);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_season_clean_sheets ON public.player_season_stats(season_id, clean_sheets DESC);

-- 4. Grant privileges
GRANT ALL PRIVILEGES ON TABLE public.match_logs TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.player_season_stats TO anon, authenticated, service_role;

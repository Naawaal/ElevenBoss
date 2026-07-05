-- supabase/migrations/007_leagues.sql

-- 1. Alter players table to add AI support columns
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS is_ai BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS ai_rating NUMERIC(5,2) DEFAULT NULL;

-- 2. Create leagues table
CREATE TABLE IF NOT EXISTS public.leagues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT UNIQUE NOT NULL REFERENCES public.guild_config(guild_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- 3. Create league_seasons table
CREATE TABLE IF NOT EXISTS public.league_seasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id UUID NOT NULL REFERENCES public.leagues(id) ON DELETE CASCADE,
    season_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    current_matchday INTEGER NOT NULL DEFAULT 1,
    total_matchdays INTEGER NOT NULL DEFAULT 0,
    duration_days INTEGER NOT NULL DEFAULT 7,
    start_time TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    end_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- 4. Create league_participants table
CREATE TABLE IF NOT EXISTS public.league_participants (
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    joined_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    PRIMARY KEY (season_id, player_id)
);

-- 5. Create league_fixtures table
CREATE TABLE IF NOT EXISTS public.league_fixtures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    matchday INTEGER NOT NULL,
    home_team_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    away_team_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    home_score INTEGER,
    away_score INTEGER,
    is_played BOOLEAN DEFAULT FALSE NOT NULL,
    played_at TIMESTAMPTZ,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- 6. Grant privileges to Supabase roles
GRANT ALL PRIVILEGES ON TABLE public.leagues TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.league_seasons TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.league_participants TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.league_fixtures TO anon, authenticated, service_role;

-- 7. Stored Procedure: Calculate Median Human Team OVR
CREATE OR REPLACE FUNCTION public.get_median_human_ovr()
RETURNS NUMERIC AS $$
DECLARE
    v_median NUMERIC;
BEGIN
    WITH team_averages AS (
        SELECT 
            sa.discord_id,
            AVG(pc.overall) as avg_rating
        FROM public.squad_assignments sa
        JOIN public.player_cards pc ON sa.player_card_id = pc.id
        JOIN public.players p ON sa.discord_id = p.discord_id
        WHERE p.is_ai = FALSE
        GROUP BY sa.discord_id
        HAVING COUNT(sa.player_card_id) = 11
    )
    SELECT COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY avg_rating), 65.0)::NUMERIC
    INTO v_median
    FROM team_averages;
    
    RETURN v_median;
END;
$$ LANGUAGE plpgsql;

-- 8. Stored Procedure: Scale AI Opponents in Season +/- 5% of Median Human OVR
CREATE OR REPLACE FUNCTION public.scale_season_ai_opponents(p_season_id UUID)
RETURNS VOID AS $$
DECLARE
    v_median NUMERIC;
    v_ai_record RECORD;
    v_random_offset NUMERIC;
BEGIN
    v_median := public.get_median_human_ovr();
    
    FOR v_ai_record IN 
        SELECT p.discord_id 
        FROM public.players p
        JOIN public.league_participants lp ON p.discord_id = lp.player_id
        WHERE lp.season_id = p_season_id AND p.is_ai = TRUE
    LOOP
        -- random() is [0, 1), so (random() * 10.0 - 5.0) / 100.0 is [-0.05, 0.05)
        v_random_offset := v_median * ((random() * 10.0 - 5.0) / 100.0);
        
        UPDATE public.players 
        SET ai_rating = ROUND(v_median + v_random_offset, 1)
        WHERE discord_id = v_ai_record.discord_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

GRANT ALL PRIVILEGES ON FUNCTION public.get_median_human_ovr TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.scale_season_ai_opponents TO anon, authenticated, service_role;

-- supabase/migrations/012_global_divisions.sql

-- 1. Create global_divisions table
CREATE TABLE IF NOT EXISTS public.global_divisions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    min_lp INTEGER NOT NULL CHECK (min_lp >= 0),
    bot_ovr_min INTEGER NOT NULL CHECK (bot_ovr_min >= 0),
    bot_ovr_max INTEGER NOT NULL CHECK (bot_ovr_max >= bot_ovr_min),
    win_coins INTEGER NOT NULL CHECK (win_coins >= 0)
);

-- 2. Add global_lp column to players table
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS global_lp INTEGER NOT NULL DEFAULT 0 CHECK (global_lp >= 0);

-- 3. Populate baseline division ranges
INSERT INTO public.global_divisions (name, min_lp, bot_ovr_min, bot_ovr_max, win_coins) VALUES
('Bronze III', 0, 50, 60, 100),
('Bronze II', 100, 55, 65, 125),
('Bronze I', 250, 60, 70, 150),
('Silver III', 500, 70, 75, 200),
('Silver II', 750, 75, 80, 250),
('Silver I', 1000, 80, 85, 300),
('Gold', 1500, 85, 90, 400),
('Elite', 2500, 90, 95, 600)
ON CONFLICT (name) DO UPDATE SET
    min_lp = EXCLUDED.min_lp,
    bot_ovr_min = EXCLUDED.bot_ovr_min,
    bot_ovr_max = EXCLUDED.bot_ovr_max,
    win_coins = EXCLUDED.win_coins;

-- 4. Grant privileges
GRANT ALL PRIVILEGES ON TABLE public.global_divisions TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON SEQUENCE public.global_divisions_id_seq TO anon, authenticated, service_role;

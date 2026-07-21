-- 072_league_time_defaults.sql
-- Align unconfigured League Time default resolution hour with 027 policy (00:00).
-- App/engine also coalesces NULL guild_config columns to UTC / 0; this seed is for
-- any readers of game_config.league_lifecycle_default_resolution_hour.

INSERT INTO public.game_config (key, value_json) VALUES
    ('league_lifecycle_default_resolution_hour', '0'::jsonb)
ON CONFLICT (key) DO UPDATE
SET value_json = EXCLUDED.value_json;

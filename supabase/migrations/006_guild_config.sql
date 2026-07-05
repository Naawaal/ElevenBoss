-- Create guild_config table
CREATE TABLE IF NOT EXISTS public.guild_config (
    guild_id BIGINT PRIMARY KEY,
    league_channel_id BIGINT NULL,
    announcement_role_id BIGINT NULL,
    league_status TEXT NOT NULL DEFAULT 'inactive',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Grant privileges to Supabase roles
GRANT ALL PRIVILEGES ON TABLE public.guild_config TO anon, authenticated, service_role;

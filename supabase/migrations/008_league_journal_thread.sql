-- supabase/migrations/008_league_journal_thread.sql

-- Alter guild_config to add league_updates_thread_id
ALTER TABLE public.guild_config ADD COLUMN IF NOT EXISTS league_updates_thread_id BIGINT NULL;

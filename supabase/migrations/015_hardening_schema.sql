-- supabase/migrations/015_hardening_schema.sql
-- US-22 / Task Group 14: schema gaps from pre-launch audit

CREATE TABLE IF NOT EXISTS public.league_members (
    guild_id      BIGINT NOT NULL,
    player_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, player_id)
);

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS training_energy INTEGER NOT NULL DEFAULT 100
        CHECK (training_energy >= 0 AND training_energy <= 100),
    ADD COLUMN IF NOT EXISTS training_energy_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS daily_drill_count INTEGER NOT NULL DEFAULT 0
        CHECK (daily_drill_count >= 0),
    ADD COLUMN IF NOT EXISTS daily_drill_reset_at DATE NOT NULL DEFAULT CURRENT_DATE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_active_evolutions_card_unique
    ON public.active_evolutions(card_id);

UPDATE public.players
SET club_name = 'Unnamed FC'
WHERE length(trim(club_name)) = 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'players_club_name_nonempty'
    ) THEN
        ALTER TABLE public.players
            ADD CONSTRAINT players_club_name_nonempty
            CHECK (length(trim(club_name)) >= 1);
    END IF;
END $$;

UPDATE public.squads
SET formation = '4-4-2'
WHERE formation NOT IN ('4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '5-3-2');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'squads_formation_valid'
    ) THEN
        ALTER TABLE public.squads
            ADD CONSTRAINT squads_formation_valid
            CHECK (formation IN ('4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '5-3-2'));
    END IF;
END $$;

GRANT ALL PRIVILEGES ON TABLE public.league_members TO anon, authenticated, service_role;

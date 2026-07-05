-- supabase/migrations/001_initial_schema.sql

-- Drop all legacy and conflicting tables (CASCADE removes dependent constraints)
DROP TABLE IF EXISTS transfer_market CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS clubs CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS player_cards CASCADE;
DROP TABLE IF EXISTS squads CASCADE;
DROP TABLE IF EXISTS squad_assignments CASCADE;
DROP TABLE IF EXISTS match_history CASCADE;

CREATE TABLE IF NOT EXISTS players (
    discord_id      BIGINT PRIMARY KEY,
    username        TEXT NOT NULL,
    club_name       TEXT NOT NULL DEFAULT '',
    manager_name    TEXT NOT NULL DEFAULT '',
    coins           INTEGER NOT NULL DEFAULT 500 CHECK (coins >= 0),
    energy          INTEGER NOT NULL DEFAULT 100 CHECK (energy >= 0 AND energy <= 100),
    max_energy      INTEGER NOT NULL DEFAULT 100 CHECK (max_energy >= 0),
    division        TEXT NOT NULL DEFAULT 'Grassroots'
                      CHECK (division IN ('Grassroots','Amateur','Semi-Pro','Professional','Elite','Legendary')),
    league_points   INTEGER NOT NULL DEFAULT 0,
    goal_difference INTEGER NOT NULL DEFAULT 0,
    matches_played  INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    draws           INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    last_claim_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_cards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    BIGINT NOT NULL REFERENCES players(discord_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    position    TEXT NOT NULL CHECK (position IN ('GK','DEF','MID','FWD')),
    rarity      TEXT NOT NULL CHECK (rarity IN ('Common','Rare','Epic','Legendary')),
    base_rating INTEGER NOT NULL,
    level       INTEGER NOT NULL DEFAULT 1,
    overall     INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS squads (
    discord_id  BIGINT PRIMARY KEY REFERENCES players(discord_id) ON DELETE CASCADE,
    formation   TEXT NOT NULL DEFAULT '4-4-2',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS squad_assignments (
    discord_id      BIGINT NOT NULL REFERENCES squads(discord_id) ON DELETE CASCADE,
    player_card_id  UUID NOT NULL REFERENCES player_cards(id) ON DELETE CASCADE,
    position_slot   INTEGER NOT NULL CHECK (position_slot >= 1 AND position_slot <= 11),
    PRIMARY KEY (discord_id, player_card_id),
    UNIQUE (discord_id, position_slot)
);

CREATE TABLE IF NOT EXISTS match_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id       BIGINT NOT NULL REFERENCES players(discord_id) ON DELETE CASCADE,
    result          TEXT NOT NULL CHECK (result IN ('win','draw','loss')),
    my_rating       NUMERIC(5,2) NOT NULL,
    opponent_rating NUMERIC(5,2) NOT NULL,
    goals_for       INTEGER NOT NULL,
    goals_against   INTEGER NOT NULL,
    coins_earned    INTEGER NOT NULL,
    points_earned   INTEGER NOT NULL,
    played_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Grant privileges to Supabase API roles (anon, authenticated, service_role)
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon, authenticated, service_role;

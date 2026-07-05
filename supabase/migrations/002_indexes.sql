-- supabase/migrations/002_indexes.sql

CREATE INDEX IF NOT EXISTS idx_player_cards_owner ON player_cards(owner_id);
CREATE INDEX IF NOT EXISTS idx_match_history_player ON match_history(player_id);
CREATE INDEX IF NOT EXISTS idx_players_division ON players(division);
CREATE INDEX IF NOT EXISTS idx_squad_assignments_card ON squad_assignments(player_card_id);

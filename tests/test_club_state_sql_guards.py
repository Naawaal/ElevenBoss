"""Source checks for US-42.3 migration 076."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "076_club_state_guards.sql"


def test_migration_076_defines_assert_and_register():
    text = MIG.read_text(encoding="utf-8")
    assert "assert_club_action_allowed" in text
    assert "CLUB_STATE:" in text
    assert "register_league_season" in text
    assert "register_league_membership" in text
    assert "touch_club_activity" in text
    assert "v_inactive_days CONSTANT INTEGER := 30" in text
    assert "v_abandoned_days CONSTANT INTEGER := 90" in text


def test_migration_wires_league_join_gate():
    text = MIG.read_text(encoding="utf-8")
    assert "assert_club_action_allowed(p_player_id, 'league_join')" in text
    assert "UNIQUE (season_id, player_id)" not in text  # uniqueness already in 070
    assert "ON CONFLICT (season_id, player_id)" in text

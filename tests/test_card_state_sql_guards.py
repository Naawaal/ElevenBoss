"""Source-level checks for US-42.2 migration 075 card-state guards."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "075_player_card_state_guards.sql"


def test_migration_defines_assert_and_card_primary_state():
    text = MIG.read_text(encoding="utf-8")
    assert "assert_card_action_allowed" in text
    assert "card_primary_state" in text
    assert "CARD_STATE:" in text
    assert "state_conflict" in text


def test_migration_wires_critical_gap_rpcs():
    text = MIG.read_text(encoding="utf-8")
    for name in (
        "admit_to_hospital",
        "process_stat_drill",
        "start_player_evolution",
        "swap_squad_players",
    ):
        assert f"FUNCTION public.{name}" in text or f"function public.{name}" in text.lower()
    assert "assert_card_action_allowed(p_owner_id, p_player_card_id, 'admit_hospital')" in text
    assert "assert_card_action_allowed(p_owner_id, p_card_id, 'drill')" in text
    assert "assert_card_action_allowed(p_owner_id, p_card_id, 'start_evolution')" in text
    assert "assert_card_action_allowed(p_discord_id, p_reserve_card_id, 'assign_xi')" in text


def test_migration_documents_fatigue_list_allow():
    text = MIG.read_text(encoding="utf-8")
    assert "fatigue alone does NOT block list" in text

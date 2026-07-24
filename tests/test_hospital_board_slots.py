# tests/test_hospital_board_slots.py
"""Hospital board overlay slot capping (042-ux-visual-refinements)."""
from __future__ import annotations

from apps.discord_bot.core.hospital_board import HOSPITAL_VISUAL_SLOTS, patient_overlay_rows


def test_empty_patients_yield_no_rows() -> None:
    assert patient_overlay_rows([]) == []


def test_caps_at_six_slots() -> None:
    patients = [
        {"player_cards": {"name": f"P{i}", "injury_tier": 1}} for i in range(8)
    ]
    rows = patient_overlay_rows(patients)
    assert len(rows) == HOSPITAL_VISUAL_SLOTS == 6
    assert [r["name"] for r in rows] == [f"P{i}" for i in range(6)]


def test_overflow_excluded_from_overlay() -> None:
    patients = [{"name": f"N{i}"} for i in range(7)]
    rows = patient_overlay_rows(patients, max_slots=6)
    assert len(rows) == 6
    assert "N6" not in [r["name"] for r in rows]

# tests/test_audit_fixes.py
"""Regression checks for audit hardening fixes (#12, #17–#20)."""
from __future__ import annotations

from match_engine import get_slot_role, reserve_fits_formation_slot


def test_reserve_fits_formation_slot_gk_only_slot_one() -> None:
    assert reserve_fits_formation_slot("4-4-2", 1, "GK")
    assert not reserve_fits_formation_slot("4-4-2", 1, "DEF")


def test_reserve_fits_formation_slot_defender_line() -> None:
    for slot in (2, 3, 4, 5):
        assert reserve_fits_formation_slot("4-4-2", slot, "DEF")
        assert get_slot_role("4-4-2", slot) == "DEF"
        assert not reserve_fits_formation_slot("4-4-2", slot, "FWD")


def test_reserve_fits_formation_slot_striker_slots() -> None:
    assert reserve_fits_formation_slot("4-4-2", 10, "FWD")
    assert not reserve_fits_formation_slot("4-4-2", 10, "MID")


def test_433_forward_line() -> None:
    for slot in (9, 10, 11):
        assert get_slot_role("4-3-3", slot) == "FWD"

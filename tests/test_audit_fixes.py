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


def test_352_wingbacks_are_mid_not_def() -> None:
    """3-5-2 LWB/RWB must match SQL formation_slot_role (MID band)."""
    for slot in (5, 6):
        assert get_slot_role("3-5-2", slot) == "MID"
        assert reserve_fits_formation_slot("3-5-2", slot, "MID")
        assert not reserve_fits_formation_slot("3-5-2", slot, "DEF")
    # 5-3-2 wingbacks stay DEF (back five)
    assert get_slot_role("5-3-2", 2) == "DEF"
    assert get_slot_role("5-3-2", 6) == "DEF"

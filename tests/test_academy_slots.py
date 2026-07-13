# tests/test_academy_slots.py
"""Academy slot caps (015)."""
from __future__ import annotations

from economy.facility_effects import academy_slot_cap


def test_slot_caps_ladder() -> None:
    assert academy_slot_cap(1) == 4
    assert academy_slot_cap(2) == 5
    assert academy_slot_cap(3) == 6
    assert academy_slot_cap(4) == 8
    assert academy_slot_cap(5) == 10


def test_slot_caps_clamp() -> None:
    assert academy_slot_cap(0) == 4
    assert academy_slot_cap(99) == 10

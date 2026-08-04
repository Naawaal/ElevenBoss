# tests/test_academy_slots.py
"""Academy slot caps (051)."""
from __future__ import annotations

from economy.facility_effects import academy_slot_cap, youth_facility_preview


def test_slot_caps_ladder() -> None:
    assert academy_slot_cap(1) == 3
    assert academy_slot_cap(2) == 3
    assert academy_slot_cap(3) == 4
    assert academy_slot_cap(4) == 4
    assert academy_slot_cap(5) == 5


def test_slot_caps_clamp() -> None:
    assert academy_slot_cap(0) == 3
    assert academy_slot_cap(99) == 5


def test_facility_preview_capacity_increases() -> None:
    prev = youth_facility_preview(3)
    assert prev is not None
    assert prev["capacity"] == (4, 4) or prev["capacity"][1] >= prev["capacity"][0]
    assert prev["range_width"][1] <= prev["range_width"][0]

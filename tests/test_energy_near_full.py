# tests/test_energy_near_full.py
"""Near-full energy gate for Store refill disable (042-ux-visual-refinements)."""
from __future__ import annotations

from energy import is_energy_near_full, near_full_reason


def test_full_at_or_above_max() -> None:
    assert near_full_reason(120, 120) == "full"
    assert near_full_reason(130, 120) == "full"
    assert is_energy_near_full(120, 120)


def test_near_within_five_of_max() -> None:
    # max 120 → within 5 starts at 115; 95% alone already covers 114 (ceil(114)=114)
    assert near_full_reason(115, 120) == "near"
    assert near_full_reason(119, 120) == "near"
    assert near_full_reason(113, 120) is None


def test_near_via_ninety_five_percent() -> None:
    # max 100 → ceil(95) = 95; within-5 also triggers at 95
    assert near_full_reason(95, 100) == "near"
    # max 200 → ceil(190) = 190; within-5 is 195 — 190 hits 95% only
    assert near_full_reason(190, 200) == "near"
    assert near_full_reason(189, 200) is None


def test_below_threshold() -> None:
    assert near_full_reason(0, 120) is None
    assert near_full_reason(50, 120) is None
    assert not is_energy_near_full(50, 120)


def test_fail_open_invalid_maximum() -> None:
    assert near_full_reason(120, 0) is None
    assert near_full_reason(120, -1) is None
    assert not is_energy_near_full(100, 0)

# tests/test_mentor_math.py
from __future__ import annotations

from player_engine import (
    L_MAX,
    MENTOR_TRANSFERS_DAILY_LIMIT,
    SP_PER_MENTOR_UNIT,
    XP_PER_MENTOR_UNIT,
    cumulative_xp_for_level,
    is_mentor_source,
    is_mentor_target,
    mentor_max_units,
    mentor_units_to_sp,
    mentor_units_to_xp,
    preview_mentor_transfer,
    sp_to_mentor_units,
    xp_headroom_to_max,
)


def test_conversion_constants() -> None:
    assert SP_PER_MENTOR_UNIT == 5
    assert XP_PER_MENTOR_UNIT == 500
    assert MENTOR_TRANSFERS_DAILY_LIMIT == 3
    assert sp_to_mentor_units(0) == 0
    assert sp_to_mentor_units(4) == 0
    assert sp_to_mentor_units(5) == 1
    assert sp_to_mentor_units(14) == 2
    assert mentor_units_to_sp(3) == 15
    assert mentor_units_to_xp(3) == 1500


def test_source_eligibility() -> None:
    assert is_mentor_source(overall=90, potential=90, skill_points=5)
    assert not is_mentor_source(overall=89, potential=90, skill_points=50)
    assert not is_mentor_source(overall=90, potential=90, skill_points=4)


def test_target_eligibility() -> None:
    assert is_mentor_target(
        overall=70, potential=85, level=24, source_id="a", target_id="b"
    )
    assert not is_mentor_target(
        overall=85, potential=85, level=24, source_id="a", target_id="b"
    )
    assert not is_mentor_target(
        overall=70, potential=85, level=L_MAX, source_id="a", target_id="b"
    )
    assert not is_mentor_target(
        overall=70, potential=85, level=24, source_id="a", target_id="a"
    )


def test_headroom_and_max_units() -> None:
    cap = cumulative_xp_for_level(L_MAX)
    assert xp_headroom_to_max(cap) == 0
    assert mentor_max_units(100, cap) == 0

    low_xp = 0
    assert mentor_max_units(5, low_xp) == 1
    assert mentor_max_units(25, low_xp) == 5
    # SP-limited
    assert mentor_max_units(7, low_xp) == 1


def test_preview_valid_and_reject_waste() -> None:
    ok = preview_mentor_transfer(source_sp=15, target_xp=0, units=3)
    assert ok.valid is True
    assert ok.sp_spent == 15
    assert ok.xp_granted == 1500
    assert ok.xp_wasted == 0
    assert ok.levels_gained >= 1

    bad = preview_mentor_transfer(source_sp=100, target_xp=cumulative_xp_for_level(L_MAX), units=1)
    assert bad.valid is False
    assert bad.xp_wasted > 0 or "headroom" in (bad.reason or "").lower() or "absorb" in (
        bad.reason or ""
    ).lower()

    over = preview_mentor_transfer(source_sp=5, target_xp=0, units=2)
    assert over.valid is False

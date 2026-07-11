# packages/player_engine/player_engine/mentor_math.py
"""Mentor Transfusion conversion math — SP → mentor units → XP (stateless)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .progression import L_MAX, cumulative_xp_for_level, simulate_apply_card_xp

SP_PER_MENTOR_UNIT = 5
XP_PER_MENTOR_UNIT = 500
MENTOR_TRANSFERS_DAILY_LIMIT = 3


class MentorTransferPreview(BaseModel):
    """Preview crossing package → Discord UI boundary."""

    valid: bool
    mentor_units: int = Field(ge=0)
    sp_spent: int = Field(ge=0)
    xp_granted: int = Field(ge=0)
    old_level: int = Field(ge=1)
    new_level: int = Field(ge=1)
    levels_gained: int = Field(ge=0)
    skill_points_granted: int = Field(ge=0)
    xp_wasted: int = Field(ge=0)
    reason: str | None = None


def sp_to_mentor_units(skill_points: int) -> int:
    return max(0, int(skill_points) // SP_PER_MENTOR_UNIT)


def mentor_units_to_sp(units: int) -> int:
    return max(0, int(units)) * SP_PER_MENTOR_UNIT


def mentor_units_to_xp(units: int) -> int:
    return max(0, int(units)) * XP_PER_MENTOR_UNIT


def is_mentor_source(*, overall: int, potential: int, skill_points: int) -> bool:
    return int(overall) >= int(potential) and int(skill_points) >= SP_PER_MENTOR_UNIT


def is_mentor_target(
    *,
    overall: int,
    potential: int,
    level: int,
    source_id: str,
    target_id: str,
) -> bool:
    if str(target_id) == str(source_id):
        return False
    return int(overall) < int(potential) and int(level) < L_MAX


def xp_headroom_to_max(current_xp: int) -> int:
    return max(0, cumulative_xp_for_level(L_MAX) - max(0, int(current_xp)))


def mentor_max_units(source_sp: int, target_xp: int) -> int:
    by_sp = sp_to_mentor_units(source_sp)
    by_xp = xp_headroom_to_max(target_xp) // XP_PER_MENTOR_UNIT
    return max(0, min(by_sp, by_xp))


def preview_mentor_transfer(
    *,
    source_sp: int,
    target_xp: int,
    units: int,
) -> MentorTransferPreview:
    n = int(units)
    if n < 1:
        return MentorTransferPreview(
            valid=False,
            mentor_units=0,
            sp_spent=0,
            xp_granted=0,
            old_level=1,
            new_level=1,
            levels_gained=0,
            skill_points_granted=0,
            xp_wasted=0,
            reason="Invalid mentor unit amount",
        )
    max_n = mentor_max_units(source_sp, target_xp)
    if n > max_n:
        sim = simulate_apply_card_xp(int(target_xp), mentor_units_to_xp(n))
        return MentorTransferPreview(
            valid=False,
            mentor_units=n,
            sp_spent=mentor_units_to_sp(n),
            xp_granted=mentor_units_to_xp(n),
            old_level=sim.old_level,
            new_level=sim.new_level,
            levels_gained=sim.levels_gained,
            skill_points_granted=sim.skill_points_granted,
            xp_wasted=sim.xp_wasted,
            reason="Requested units exceed convertible SP or target XP headroom",
        )
    xp_amt = mentor_units_to_xp(n)
    sim = simulate_apply_card_xp(int(target_xp), xp_amt)
    if sim.xp_wasted > 0:
        return MentorTransferPreview(
            valid=False,
            mentor_units=n,
            sp_spent=mentor_units_to_sp(n),
            xp_granted=xp_amt,
            old_level=sim.old_level,
            new_level=sim.new_level,
            levels_gained=sim.levels_gained,
            skill_points_granted=sim.skill_points_granted,
            xp_wasted=sim.xp_wasted,
            reason="Target cannot absorb mentor XP",
        )
    return MentorTransferPreview(
        valid=True,
        mentor_units=n,
        sp_spent=mentor_units_to_sp(n),
        xp_granted=xp_amt,
        old_level=sim.old_level,
        new_level=sim.new_level,
        levels_gained=sim.levels_gained,
        skill_points_granted=sim.skill_points_granted,
        xp_wasted=0,
        reason=None,
    )

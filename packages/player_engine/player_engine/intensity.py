# packages/player_engine/player_engine/intensity.py
"""Division Rank → fatigue/injury intensity tier (016)."""
from __future__ import annotations

from typing import Literal

IntensityTier = Literal[1, 2, 3]

DIVISION_INTENSITY_TIER: dict[str, IntensityTier] = {
    "Grassroots": 1,
    "Amateur": 1,
    "Semi-Pro": 2,
    "Professional": 2,
    "Elite": 3,
    "Legendary": 3,
}

INTENSITY_LABELS: dict[int, str] = {
    1: "Low",
    2: "Medium",
    3: "High",
}

INTENSITY_VIBE: dict[int, str] = {
    1: "Forgiving",
    2: "Rotation recommended",
    3: "Deep squad required",
}


def intensity_tier_for_division(division: str | None) -> IntensityTier:
    """Map settled Division Rank to intensity 1–3; unknown → Tier 1."""
    if not division:
        return 1
    return DIVISION_INTENSITY_TIER.get(str(division), 1)


def intensity_label(tier: int) -> str:
    return INTENSITY_LABELS.get(int(tier), "Low")


def intensity_vibe(tier: int) -> str:
    return INTENSITY_VIBE.get(int(tier), INTENSITY_VIBE[1])


def clamp_intensity_tier(tier: int | None) -> IntensityTier:
    t = int(tier or 1)
    if t <= 1:
        return 1
    if t >= 3:
        return 3
    return 2  # type: ignore[return-value]

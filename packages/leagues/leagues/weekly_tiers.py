# packages/leagues/leagues/weekly_tiers.py
"""Weekly Division Rank tier thresholds and coin rewards (US-30)."""
from __future__ import annotations

from datetime import datetime, timezone

TIER_BRONZE = "bronze"
TIER_SILVER = "silver"
TIER_GOLD = "gold"

TIER_ORDER: tuple[str, ...] = (TIER_BRONZE, TIER_SILVER, TIER_GOLD)

DEFAULT_THRESHOLDS: dict[str, int] = {
    TIER_BRONZE: 6,
    TIER_SILVER: 12,
    TIER_GOLD: 18,
}

# Mirrors economy.flows.DIVISION_TIERS — keep in sync
_DIVISION_TIERS: dict[str, int] = {
    "Grassroots": 0,
    "Amateur": 1,
    "Semi-Pro": 2,
    "Professional": 3,
    "Elite": 4,
    "Legendary": 5,
}


def _division_tier(division: str) -> int:
    return _DIVISION_TIERS.get(division or "Grassroots", 0)


def iso_week_utc(now_utc: datetime | None = None) -> str:
    """ISO week key — matches Postgres `to_char(..., 'IYYY-"W"IW')` (zero-padded week)."""
    now = now_utc or datetime.now(timezone.utc)
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def weekly_tier_coin_reward(tier: str, division: str) -> int:
    """Coin payout for claiming a weekly tier; scales by server division."""
    tier_idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
    div_tier = _division_tier(division)
    bases = (50, 100, 200)
    mults = (25, 50, 75)
    return bases[tier_idx] + div_tier * mults[tier_idx]


def tiers_reached(weekly_pts: int, thresholds: dict[str, int] | None = None) -> list[str]:
    """Tiers the player has earned based on current weekly points."""
    th = thresholds or DEFAULT_THRESHOLDS
    return [t for t in TIER_ORDER if weekly_pts >= th.get(t, 999)]


def highest_unclaimed_tier(
    weekly_pts: int,
    claimed_tiers: set[str],
    thresholds: dict[str, int] | None = None,
) -> str | None:
    """Highest tier earned but not yet claimed, or None."""
    reached = tiers_reached(weekly_pts, thresholds)
    for tier in reversed(reached):
        if tier not in claimed_tiers:
            return tier
    return None


def tier_progress_label(weekly_pts: int, thresholds: dict[str, int] | None = None) -> str:
    """Compact progress string for embeds."""
    th = thresholds or DEFAULT_THRESHOLDS
    parts: list[str] = []
    for tier in TIER_ORDER:
        need = th.get(tier, 0)
        if weekly_pts >= need:
            parts.append(f"{tier.title()} ✓")
        else:
            parts.append(f"{weekly_pts}/{need} {tier.title()}")
            break
    return " · ".join(parts)

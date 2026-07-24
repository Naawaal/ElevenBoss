# packages/energy/energy/near_full.py
"""Near-full action-energy gate for store refill UX (no Discord / DB)."""
from __future__ import annotations

from math import ceil
from typing import Literal

NearFullReason = Literal["full", "near"]


def near_full_reason(current: int, maximum: int) -> NearFullReason | None:
    """Return why refill should be disabled, or None if purchase stays available.

    Fail-open when maximum is missing/non-positive so a bad config never locks
    the button forever (purchase RPC remains the safety net).
    """
    try:
        cur = int(current)
        mx = int(maximum)
    except (TypeError, ValueError):
        return None
    if mx <= 0:
        return None
    if cur >= mx:
        return "full"
    if cur >= ceil(0.95 * mx) or cur >= mx - 5:
        return "near"
    return None


def is_energy_near_full(current: int, maximum: int) -> bool:
    return near_full_reason(current, maximum) is not None

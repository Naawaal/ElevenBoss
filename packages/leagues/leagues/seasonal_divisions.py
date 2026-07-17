# packages/leagues/leagues/seasonal_divisions.py
"""Seasonal division seating and fixed top/bottom promotion (not weekly 20%)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class FixedPromoResult:
    promoted_ids: list[int]
    relegated_ids: list[int]
    retained_ids: list[int]


def seat_humans_into_divisions(
    human_ids_ordered: Sequence[int],
    clubs_per_div: int = 8,
) -> list[list[int]]:
    """Chunk humans into tiers of at most ``clubs_per_div`` (overflow → next tier)."""
    if clubs_per_div < 1:
        raise ValueError("clubs_per_div must be >= 1")
    ids = [int(x) for x in human_ids_ordered]
    if not ids:
        return []
    tiers: list[list[int]] = []
    for i in range(0, len(ids), clubs_per_div):
        tiers.append(ids[i : i + clubs_per_div])
    return tiers


def compute_fixed_promo_relegation(
    human_standings_sorted: Sequence[int],
    spots: int = 2,
) -> FixedPromoResult:
    """
    Fixed top/bottom promo for one table of human club ids already sorted
    best→worst (Pts→GD→GF). Skips when n < 4.
    """
    sorted_ids = [int(x) for x in human_standings_sorted]
    n = len(sorted_ids)
    if n < 4 or spots < 1:
        return FixedPromoResult(promoted_ids=[], relegated_ids=[], retained_ids=sorted_ids)

    k = min(spots, n // 2)
    if 2 * k > n:
        k = 1
    promoted = sorted_ids[:k]
    relegated = sorted_ids[n - k :]
    retained = sorted_ids[k : n - k]
    return FixedPromoResult(
        promoted_ids=promoted,
        relegated_ids=relegated,
        retained_ids=retained,
    )

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


@dataclass(frozen=True)
class HumanFirstPromoResult:
    champion_id: int | None
    promoted_ids: list[int]
    relegated_ids: list[int]
    retained_ids: list[int]
    spots_used: int


def compute_human_first_promo_relegation(
    human_standings_sorted: Sequence[int],
    *,
    spots: int = 2,
    eligible_ids: Sequence[int] | None = None,
    min_humans_for_full_movement: int = 4,
) -> HumanFirstPromoResult:
    """
    Positions 1 champion+promoted, 2 promoted, 7–8 relegated for 8-club tables,
    but only among **humans**. Bots never consume promo slots.

    When too few humans, reduce ``spots`` rather than force full 2-up/2-down.
    ``eligible_ids`` filters promo eligibility (e.g. exclude double_forfeit-only clubs).
    """
    sorted_ids = [int(x) for x in human_standings_sorted]
    if eligible_ids is not None:
        allow = {int(x) for x in eligible_ids}
        ranked = [i for i in sorted_ids if i in allow]
    else:
        ranked = list(sorted_ids)

    n = len(ranked)
    if n < min_humans_for_full_movement or spots < 1:
        return HumanFirstPromoResult(
            champion_id=ranked[0] if ranked else None,
            promoted_ids=[],
            relegated_ids=[],
            retained_ids=list(sorted_ids),
            spots_used=0,
        )

    k = min(spots, n // 2)
    if 2 * k > n:
        k = 1
    promoted = ranked[:k]
    relegated = ranked[n - k :]
    retained = [i for i in sorted_ids if i not in promoted and i not in relegated]
    # Invariant: promo and releg sets never overlap
    assert not (set(promoted) & set(relegated))
    return HumanFirstPromoResult(
        champion_id=promoted[0] if promoted else None,
        promoted_ids=promoted,
        relegated_ids=relegated,
        retained_ids=retained,
        spots_used=k,
    )


def counts_for_promo_eligibility(result_type: str | None) -> bool:
    """Double forfeit and void do not count toward promo eligibility matches."""
    if not result_type:
        return True
    return result_type not in ("double_forfeit", "void")

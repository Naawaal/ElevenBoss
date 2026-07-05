# packages/leagues/leagues/calculator.py
from __future__ import annotations
from .models import LeagueEntry, PromotionResult

def compute_promotions_relegations(entries: list[LeagueEntry]) -> PromotionResult:
    """
    Computes promotion, relegation, and retention lists for a league table:
    - Sorts entries by league_points descending, then by goal_difference descending.
    - Top 20% (minimum 1) are promoted.
    - Bottom 20% (minimum 1) are relegated.
    - Ensures no overlap (mutual exclusivity).
    """
    n = len(entries)
    if n == 0:
        return PromotionResult(promoted_ids=[], relegated_ids=[], retained_ids=[])

    # Sort descending by points, then by goal difference
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.league_points, e.goal_difference),
        reverse=True
    )
    sorted_ids = [e.discord_id for e in sorted_entries]

    if n == 1:
        # Edge case: single entry cannot be promoted or relegated with overlap
        return PromotionResult(promoted_ids=[], relegated_ids=[], retained_ids=sorted_ids)

    # Calculate 20% targets
    num_promoted = max(1, int(round(n * 0.20)))
    num_relegated = max(1, int(round(n * 0.20)))

    # Prevent overlap
    if num_promoted + num_relegated > n:
        num_promoted = 1
        num_relegated = 1

    promoted_ids = sorted_ids[:num_promoted]
    relegated_ids = sorted_ids[n - num_relegated:]
    retained_ids = sorted_ids[num_promoted:n - num_relegated]

    return PromotionResult(
        promoted_ids=promoted_ids,
        relegated_ids=relegated_ids,
        retained_ids=retained_ids,
    )

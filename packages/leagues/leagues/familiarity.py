# packages/leagues/leagues/familiarity.py
"""Lineup continuity bonus for league matches (US-26)."""
from __future__ import annotations

DEFAULT_BONUS_PCT = 2.0
DEFAULT_MIN_MATCHDAYS = 3
ROTATION_PENALTY_PCT = 1.0


def familiarity_multiplier(
    same_xi_matchdays: int,
    *,
    bonus_pct: float = DEFAULT_BONUS_PCT,
    min_matchdays: int = DEFAULT_MIN_MATCHDAYS,
    heavy_rotation: bool = False,
) -> float:
    """
    Returns rating multiplier (1.0 = neutral).
    same_xi_matchdays: consecutive matchdays with identical XI card IDs.
    """
    mult = 1.0
    if same_xi_matchdays >= min_matchdays:
        mult += bonus_pct / 100.0
    if heavy_rotation:
        mult -= ROTATION_PENALTY_PCT / 100.0
    return max(0.95, min(1.05, mult))


def count_same_xi_streak(card_id_sets: list[frozenset]) -> int:
    """Count consecutive identical XI sets from most recent backward."""
    if not card_id_sets:
        return 0
    streak = 1
    for i in range(len(card_id_sets) - 1, 0, -1):
        if card_id_sets[i] == card_id_sets[i - 1]:
            streak += 1
        else:
            break
    return streak


def xi_streak_including_current(history_sets: list[frozenset], current: frozenset) -> int:
    """Streak of identical XIs ending with current lineup (inclusive)."""
    if not current:
        return 0
    return count_same_xi_streak(history_sets + [current])

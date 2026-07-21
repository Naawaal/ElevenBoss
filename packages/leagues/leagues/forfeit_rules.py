# packages/leagues/leagues/forfeit_rules.py
"""Forfeit and double-forfeit standings deltas (026 Q2)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClubStatDelta:
    matches_played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    counts_as_draw: bool = False
    counts_as_clean_sheet: bool = False
    counts_as_unbeaten: bool = False
    counts_as_appearance: bool = False
    counts_for_promo_eligibility: bool = False
    result_type: str = "settled"


@dataclass(frozen=True)
class ForfeitOutcome:
    home_score: int
    away_score: int
    result_type: str
    home: ClubStatDelta
    away: ClubStatDelta


def single_forfeit(*, illegal_is_home: bool) -> ForfeitOutcome:
    """Legal club wins 3–0; illegal club loses."""
    if illegal_is_home:
        home = ClubStatDelta(
            matches_played=1,
            lost=1,
            goals_for=0,
            goals_against=3,
            points=0,
            result_type="forfeit",
            counts_for_promo_eligibility=False,
        )
        away = ClubStatDelta(
            matches_played=1,
            won=1,
            goals_for=3,
            goals_against=0,
            points=3,
            counts_as_clean_sheet=True,
            counts_as_unbeaten=True,
            counts_as_appearance=True,
            counts_for_promo_eligibility=True,
            result_type="forfeit",
        )
        return ForfeitOutcome(0, 3, "forfeit", home, away)
    home = ClubStatDelta(
        matches_played=1,
        won=1,
        goals_for=3,
        goals_against=0,
        points=3,
        counts_as_clean_sheet=True,
        counts_as_unbeaten=True,
        counts_as_appearance=True,
        counts_for_promo_eligibility=True,
        result_type="forfeit",
    )
    away = ClubStatDelta(
        matches_played=1,
        lost=1,
        goals_for=0,
        goals_against=3,
        points=0,
        result_type="forfeit",
        counts_for_promo_eligibility=False,
    )
    return ForfeitOutcome(3, 0, "forfeit", home, away)


def double_forfeit() -> ForfeitOutcome:
    """
    0–0 double forfeit: both MP+1, L+1, 0 pts.
    Not a draw, clean sheet, unbeaten, appearance, or promo-eligible match.
    """
    delta = ClubStatDelta(
        matches_played=1,
        lost=1,
        goals_for=0,
        goals_against=0,
        points=0,
        counts_as_draw=False,
        counts_as_clean_sheet=False,
        counts_as_unbeaten=False,
        counts_as_appearance=False,
        counts_for_promo_eligibility=False,
        result_type="double_forfeit",
    )
    return ForfeitOutcome(0, 0, "double_forfeit", delta, delta)

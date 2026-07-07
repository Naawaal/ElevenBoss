# packages/leagues/leagues/match_points.py
"""Canonical match point formulas — Division Rank, Global LP, Season Pts (US-30)."""
from __future__ import annotations

FOOTBALL_PTS: dict[str, int] = {"win": 3, "draw": 1, "loss": 0}
GLOBAL_LP_DELTA: dict[str, int] = {"win": 15, "draw": 5, "loss": -10}


def division_rank_points(result: str) -> int:
    return FOOTBALL_PTS.get(result, 0)


def season_fixture_points(result: str) -> int:
    return division_rank_points(result)


def global_lp_delta(result: str) -> int:
    return GLOBAL_LP_DELTA.get(result, 0)


def clamp_global_lp(current: int, delta: int) -> tuple[int, int]:
    """Return (new_lp, actual_delta) with floor at 0."""
    new_lp = max(0, current + delta)
    return new_lp, new_lp - current

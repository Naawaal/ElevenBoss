# packages/leagues/leagues/cutover.py
"""Lifecycle V1 cutover / grandfather predicates (pure)."""
from __future__ import annotations

from typing import Sequence

from .lifecycle_states import OPEN_SEASON_STATUSES, PACING_LIFECYCLE_V1, RULESET_LIFECYCLE_V1


def lifecycle_v1_effective(*, global_flag: bool, guild_flag: bool | None) -> bool:
    """global AND (guild IS NULL OR guild IS TRUE)."""
    if not global_flag:
        return False
    if guild_flag is False:
        return False
    return True


def is_lifecycle_v1_season(season: dict) -> bool:
    pacing = (season.get("pacing_mode") or "").strip()
    ruleset = (season.get("ruleset_version") or "").strip()
    return pacing == PACING_LIFECYCLE_V1 or ruleset == RULESET_LIFECYCLE_V1


def has_blocking_non_v1_open_season(seasons: Sequence[dict]) -> bool:
    """True if any open season is not Lifecycle V1 (blocks new V1 start)."""
    for s in seasons:
        status = (s.get("status") or "").strip()
        if status not in OPEN_SEASON_STATUSES:
            continue
        if not is_lifecycle_v1_season(s):
            return True
    return False


def can_start_v1_season(*, effective_cutover: bool, open_seasons: Sequence[dict]) -> bool:
    if not effective_cutover:
        return False
    if has_blocking_non_v1_open_season(open_seasons):
        return False
    # Also block if another open V1 season already exists
    for s in open_seasons:
        status = (s.get("status") or "").strip()
        if status in OPEN_SEASON_STATUSES:
            return False
    return True

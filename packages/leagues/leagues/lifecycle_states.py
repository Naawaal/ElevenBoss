# packages/leagues/leagues/lifecycle_states.py
"""Season / matchday / fixture status enums and allowed transitions (026)."""
from __future__ import annotations

from typing import Final

# Grandfather 020/021 values remain valid alongside V1.
SEASON_STATUSES: Final[frozenset[str]] = frozenset({
    "dormant",
    "registration",  # legacy alias for registration_open
    "registration_open",
    "registration_locked",
    "preparing",
    "active",
    "paused",
    "settling",
    "completed",
    "cancelled",
    "failed",
})

MATCHDAY_STATUSES: Final[frozenset[str]] = frozenset({
    "scheduled",
    "open",
    "closing_soon",
    "locked",
    "resolving",
    "completed",
    "resolution_failed",
})

FIXTURE_STATUSES: Final[frozenset[str]] = frozenset({
    "scheduled",
    "available",
    "running",
    "settling",
    "settled",
    "forfeit",
    "void",
    "failed_retryable",
})

FIXTURE_TERMINAL: Final[frozenset[str]] = frozenset({
    "settled",
    "forfeit",
    "void",
})

RESULT_TYPES: Final[frozenset[str]] = frozenset({
    "settled",
    "forfeit",
    "double_forfeit",
    "void",
})

PACING_LIFECYCLE_V1: Final[str] = "lifecycle_v1"
RULESET_LIFECYCLE_V1: Final[str] = "lifecycle-v1"

# from → allowed to
SEASON_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "dormant": frozenset({"registration_open", "registration"}),
    "registration": frozenset({"registration_locked", "cancelled", "active"}),  # legacy path may jump
    "registration_open": frozenset({"registration_locked", "cancelled"}),
    "registration_locked": frozenset({"preparing", "cancelled"}),
    "preparing": frozenset({"active", "failed", "cancelled"}),
    "failed": frozenset({"preparing", "cancelled"}),
    "active": frozenset({"paused", "settling", "cancelled"}),
    "paused": frozenset({"active", "cancelled"}),
    "settling": frozenset({"completed", "cancelled"}),
    "completed": frozenset({"registration_open", "dormant"}),
    "cancelled": frozenset({"registration_open", "dormant"}),
}

MATCHDAY_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "scheduled": frozenset({"open"}),
    "open": frozenset({"closing_soon", "locked"}),
    "closing_soon": frozenset({"locked"}),
    "locked": frozenset({"resolving"}),
    "resolving": frozenset({"completed", "resolution_failed"}),
    "resolution_failed": frozenset({"resolving"}),
    "completed": frozenset(),
}

OPEN_SEASON_STATUSES: Final[frozenset[str]] = frozenset({
    "registration",
    "registration_open",
    "registration_locked",
    "preparing",
    "active",
    "paused",
    "settling",
    "failed",
})

# Hub / Season standings: prefer in-play over leftover registration from an older season.
# Lower index = higher priority. Same rank → newest created_at wins.
_OPEN_SEASON_DISPLAY_PRIORITY: Final[tuple[str, ...]] = (
    "active",
    "paused",
    "settling",
    "preparing",
    "failed",
    "registration_locked",
    "registration_open",
    "registration",
)


def can_transition_season(current: str, nxt: str) -> bool:
    return nxt in SEASON_TRANSITIONS.get(current, frozenset())


def can_transition_matchday(current: str, nxt: str) -> bool:
    return nxt in MATCHDAY_TRANSITIONS.get(current, frozenset())


def is_fixture_terminal(status: str) -> bool:
    return status in FIXTURE_TERMINAL


def is_open_season_status(status: str) -> bool:
    return status in OPEN_SEASON_STATUSES


def prefer_open_league_season(seasons: list[dict]) -> dict | None:
    """Choose which open season the hub / Season standings should show.

    Avoids picking a stale ``registration`` row when a newer ``active`` season exists
    (or the reverse: prefer ``active`` even if an older leftover registration remains).
    """
    best: dict | None = None
    best_rank = len(_OPEN_SEASON_DISPLAY_PRIORITY)
    best_created = ""
    for season in seasons:
        status = str(season.get("status") or "")
        if status not in OPEN_SEASON_STATUSES:
            continue
        try:
            rank = _OPEN_SEASON_DISPLAY_PRIORITY.index(status)
        except ValueError:
            continue
        created = str(season.get("created_at") or "")
        if rank < best_rank or (rank == best_rank and created > best_created):
            best = season
            best_rank = rank
            best_created = created
    return best


def normalize_registration_status(status: str) -> str:
    """Map legacy ``registration`` to V1 ``registration_open`` for comparisons."""
    if status == "registration":
        return "registration_open"
    return status

"""US-42.3 club soft lifecycle + action matrix (pure).

Durable classify/recover/touch live in migration 074 RPCs
(`classify_club_identity_status`, `recover_club_identity`, `touch_club_activity`).
This module mirrors thresholds and the club action matrix for tests/UI hints only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .identity import (
    ABANDONED_DAYS,
    INACTIVE_DAYS,
    IdentityStatus,
    classify_status,
)

ClubKind = Literal["Human", "AI"]
SoftLifecycle = Literal["Active", "Inactive", "Abandoned"]
ClubOverlay = Literal["MatchLocked", "LeagueSeated"]

ClubAction = Literal[
    "view_hub",
    "recover",
    "store_faucet",
    "development_mutate",
    "squad_mutate",
    "market_mutate",
    "match_start",
    "league_join",
    "league_remain",
]

# Soft status → IdentityStatus storage values
_SOFT_TO_STORAGE = {
    "Active": "active",
    "Inactive": "inactive",
    "Abandoned": "abandoned",
}
_STORAGE_TO_SOFT: dict[str, SoftLifecycle] = {
    "active": "Active",
    "inactive": "Inactive",
    "abandoned": "Abandoned",
}

_MUTATIONS = frozenset(
    {
        "recover",
        "store_faucet",
        "development_mutate",
        "squad_mutate",
        "market_mutate",
        "match_start",
        "league_join",
    }
)

_AI_BLOCKED = frozenset(
    {
        "store_faucet",
        "development_mutate",
        "squad_mutate",
        "market_mutate",
        "match_start",
        "league_join",
        "recover",
    }
)


def derive_club_kind(*, is_ai: bool) -> ClubKind:
    return "AI" if is_ai else "Human"


def soft_lifecycle_from_activity(
    last_activity: datetime,
    now: datetime | None = None,
    *,
    inactive_days: int = INACTIVE_DAYS,
    abandoned_days: int = ABANDONED_DAYS,
) -> SoftLifecycle:
    """Human soft primary from last qualifying activity (mirrors identity.classify_status)."""
    status: IdentityStatus = classify_status(
        last_activity,
        now,
        inactive_days=inactive_days,
        abandoned_days=abandoned_days,
    )
    return _STORAGE_TO_SOFT[status]


def soft_lifecycle_from_storage(identity_status: str | None) -> SoftLifecycle:
    if not identity_status:
        return "Active"
    return _STORAGE_TO_SOFT.get(identity_status.lower(), "Active")


def derive_overlays(
    *,
    match_locked: bool = False,
    league_seated: bool = False,
) -> set[ClubOverlay]:
    out: set[ClubOverlay] = set()
    if match_locked:
        out.add("MatchLocked")
    if league_seated:
        out.add("LeagueSeated")
    return out


def can_perform_club_action(
    soft: SoftLifecycle,
    *,
    kind: ClubKind = "Human",
    match_locked: bool = False,
    action: str,
) -> tuple[bool, str]:
    """
    Club action matrix (spec §B.5).
    Returns (allowed, reason). reason '' when allowed.
    """
    if action == "view_hub":
        return True, ""

    if kind == "AI" and action in _AI_BLOCKED:
        return False, f"CLUB_STATE: AI blocks {action}"

    if action == "league_remain":
        return True, ""

    if match_locked and action in (
        "development_mutate",
        "squad_mutate",
        "market_mutate",
        "match_start",
        "league_join",
    ):
        return False, f"CLUB_STATE: MatchLocked blocks {action}"
    # store_faucet / recover Allowed under MatchLocked per matrix

    if action == "recover":
        if soft in ("Inactive", "Abandoned"):
            return True, ""
        return False, "CLUB_STATE: Active blocks recover"

    if action == "league_join":
        if soft in ("Inactive", "Abandoned"):
            return False, f"CLUB_STATE: {soft} blocks league_join"
        return True, ""

    if action in (
        "store_faucet",
        "development_mutate",
        "squad_mutate",
        "market_mutate",
        "match_start",
    ):
        # Soft Inactive/Abandoned still Allow progression/economy (spec matrix)
        return True, ""

    # Default: Block unknown for busy soft entry actions
    if soft in ("Inactive", "Abandoned") and action not in (
        "view_hub",
        "recover",
        "store_faucet",
        "development_mutate",
        "squad_mutate",
        "market_mutate",
        "match_start",
        "league_remain",
    ):
        return False, f"CLUB_STATE: {soft} blocks {action}"

    return True, ""

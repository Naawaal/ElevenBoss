# apps/discord_bot/core/squad_validity.py
"""Starting-XI validity checks for match gates (retirement / incomplete lineup)."""
from __future__ import annotations

from typing import Any

RETIREMENT_XI_MSG = (
    "Your starting XI is invalid due to a recent retirement. "
    "Please visit `/squad` to set your lineup."
)


def incomplete_xi_msg(count: int) -> str:
    return (
        f"Your starting squad must have exactly **11 players** assigned "
        f"(current: **{count}/11**).\n"
        "Configure your starting 11 using `/squad` first."
    )


async def fetch_xi_state(db: Any, discord_id: int) -> tuple[int, bool]:
    """Return (assignment_count, squad_invalid)."""
    assignments_res = (
        await db.table("squad_assignments")
        .select("player_card_id")
        .eq("discord_id", discord_id)
        .execute()
    )
    count = len(assignments_res.data or [])
    player_res = (
        await db.table("players")
        .select("squad_invalid")
        .eq("discord_id", discord_id)
        .maybe_single()
        .execute()
    )
    invalid = bool((player_res.data or {}).get("squad_invalid"))
    return count, invalid


def xi_block_message(count: int, squad_invalid: bool) -> str | None:
    """Manager-facing block copy, or None if XI is match-ready."""
    if count == 11 and not squad_invalid:
        return None
    if squad_invalid:
        return RETIREMENT_XI_MSG
    return incomplete_xi_msg(count)


async def human_club_xi_ok(db: Any, discord_id: int, card_count: int | None = None) -> bool:
    """True when a human club may enter a match (11 starters and not squad_invalid)."""
    if card_count is None:
        count, invalid = await fetch_xi_state(db, discord_id)
    else:
        count = card_count
        player_res = (
            await db.table("players")
            .select("squad_invalid")
            .eq("discord_id", discord_id)
            .maybe_single()
            .execute()
        )
        invalid = bool((player_res.data or {}).get("squad_invalid"))
    return count == 11 and not invalid

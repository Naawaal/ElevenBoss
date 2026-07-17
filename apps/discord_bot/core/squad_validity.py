# apps/discord_bot/core/squad_validity.py
"""Starting-XI validity checks for match gates (retirement / incomplete lineup / contracts)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from economy.wages import contract_blocks_xi
from apps.discord_bot.core.economy_rpc import get_game_config_int

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


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


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
    """Manager-facing block copy, or None if XI is match-ready (ignores contracts)."""
    if count == 11 and not squad_invalid:
        return None
    if squad_invalid:
        return RETIREMENT_XI_MSG
    return incomplete_xi_msg(count)


async def fetch_contract_xi_block(db: Any, discord_id: int) -> str | None:
    """Past-grace contracts in Starting XI — renew or replace required."""
    grace_days = await get_game_config_int(db, "contract_grace_days", 7)
    assignments_res = (
        await db.table("squad_assignments")
        .select("player_cards(id, name, contract_expires_at)")
        .eq("discord_id", discord_id)
        .execute()
    )
    now = datetime.now(timezone.utc)
    blocked: list[str] = []
    for row in assignments_res.data or []:
        card = row.get("player_cards") or {}
        exp = _parse_ts(card.get("contract_expires_at"))
        if exp is None:
            continue
        if contract_blocks_xi(exp, now, grace_days=grace_days):
            blocked.append(str(card.get("name") or "Unknown"))
    if not blocked:
        return None
    names = ", ".join(f"**{n}**" for n in blocked[:5])
    extra = f" (+{len(blocked) - 5} more)" if len(blocked) > 5 else ""
    return (
        f"Contract expired (past grace): {names}{extra}. "
        "Renew on `/player-profile` or replace via `/squad` before matching."
    )


async def card_contract_blocks_assign(db: Any, card: dict) -> str | None:
    """Reject assigning a single past-grace card into Starting XI."""
    grace_days = await get_game_config_int(db, "contract_grace_days", 7)
    exp = _parse_ts(card.get("contract_expires_at"))
    if exp is None:
        return None
    now = datetime.now(timezone.utc)
    if not contract_blocks_xi(exp, now, grace_days=grace_days):
        return None
    name = card.get("name") or "Player"
    return (
        f"**{name}**'s contract is past grace. Renew on `/player-profile` "
        "before assigning them to the Starting XI."
    )


async def club_xi_block_reason(db: Any, discord_id: int, card_count: int | None = None) -> str | None:
    """Full match gate: incomplete XI, retirement hole, or past-grace contracts."""
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
    msg = xi_block_message(count, invalid)
    if msg:
        return msg
    return await fetch_contract_xi_block(db, discord_id)


async def human_club_xi_ok(db: Any, discord_id: int, card_count: int | None = None) -> bool:
    """True when a human club may enter a match (11 starters, not squad_invalid, contracts OK)."""
    return (await club_xi_block_reason(db, discord_id, card_count=card_count)) is None

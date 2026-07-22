# apps/discord_bot/core/club_rpc.py
"""Thin Supabase wrappers for US-42.3 club state / league join RPCs."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def register_league_season(
    db: Any,
    player_id: int,
    guild_id: int,
    season_id: str,
    eligibility: dict | None = None,
) -> dict:
    res = await db.rpc(
        "register_league_season",
        {
            "p_player_id": player_id,
            "p_guild_id": guild_id,
            "p_season_id": season_id,
            "p_eligibility": eligibility or {},
        },
    ).execute()
    data = res.data
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], dict) else {"raw": data}
    return data or {}


async def register_league_membership(
    db: Any,
    player_id: int,
    guild_id: int,
) -> dict:
    res = await db.rpc(
        "register_league_membership",
        {"p_player_id": player_id, "p_guild_id": guild_id},
    ).execute()
    data = res.data
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], dict) else {"raw": data}
    return data or {}


def club_state_error_message(exc: BaseException) -> str | None:
    """Map CLUB_STATE / eligibility RPC errors to manager-facing copy."""
    text = str(exc)
    if "CLUB_STATE:" in text:
        if "blocks league_join" in text or "Inactive" in text or "Abandoned" in text:
            return (
                "Your club is marked **Inactive** or **Abandoned** after a long quiet spell. "
                "Play a match, train, or claim a store bonus first — then join the league again."
            )
        if "AI blocks" in text:
            return "AI clubs cannot register for human league seats."
        if "MatchLocked" in text or "locked in an active match" in text.lower():
            return "Finish or wait out your active match before joining the league."
        # strip SQL prefix noise
        idx = text.find("CLUB_STATE:")
        return text[idx:].split("\n")[0][:180]
    if "career matches" in text.lower():
        return text.split("\n")[0][:200]
    if "at least" in text.lower() and "days" in text.lower():
        return text.split("\n")[0][:200]
    if "registration is closed" in text.lower():
        return "Season registration is closed."
    if "Season not found" in text or "League not found" in text:
        return "No open league season found for this server."
    return None

# apps/discord_bot/middleware/match_lock.py
from __future__ import annotations

from supabase import AsyncClient


async def is_in_match(db: AsyncClient, discord_id: int) -> bool:
    res = await db.table("match_locks").select("discord_id").eq("discord_id", discord_id).maybe_single().execute()
    return bool(res and res.data)


async def assert_not_in_match(db: AsyncClient, discord_id: int) -> str | None:
    """Returns an error message if locked, else None."""
    if await is_in_match(db, discord_id):
        return "You are currently locked in an active match. Finish or wait for it to end first."
    return None

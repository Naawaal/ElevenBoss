# apps/discord_bot/middleware/match_lock.py
from __future__ import annotations

from supabase import AsyncClient


async def is_in_match(db: AsyncClient, discord_id: int) -> bool:
    res = await db.table("match_locks").select("discord_id").eq("discord_id", discord_id).maybe_single().execute()
    return bool(res and res.data)


async def acquire_match_lock(db: AsyncClient, discord_id: int, lock_type: str) -> bool:
    """Atomically acquire a match lock. Returns True if acquired."""
    res = await db.rpc(
        "acquire_match_lock",
        {"p_discord_id": discord_id, "p_lock_type": lock_type},
    ).execute()
    return bool(res.data)


async def release_match_lock(db: AsyncClient, discord_id: int) -> None:
    await db.rpc("release_match_lock", {"p_discord_id": discord_id}).execute()


async def abandon_match_run(db: AsyncClient, run_id: str, *, reason: str | None = None):
    """Proxy to match_runs.abandon_match_run (status + lock release)."""
    from apps.discord_bot.core.match_runs import abandon_match_run as _abandon

    return await _abandon(db, run_id, reason=reason)


async def reconcile_orphaned_match_locks(db: AsyncClient) -> int:
    from apps.discord_bot.core.match_runs import reconcile_orphaned_match_locks as _reconcile

    return await _reconcile(db)


async def assert_not_in_match(db: AsyncClient, discord_id: int) -> str | None:
    """Returns an error message if locked, else None."""
    if await is_in_match(db, discord_id):
        return "You are currently locked in an active match. Finish or wait for it to end first."
    return None

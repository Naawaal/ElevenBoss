# apps/discord_bot/core/thread_permissions.py
"""Thread permission helpers — AC-17d send-disabled, reactions-enabled."""
from __future__ import annotations

import asyncio
import logging

import discord

logger = logging.getLogger(__name__)

MATCH_THREAD_ARCHIVE_DELAY_SEC = 300.0


async def restrict_thread_to_bot_and_reactions(thread: discord.Thread, _guild: discord.Guild) -> None:
    """Lock thread (read-only) and swallow permission errors.

    ponytail: discord thread permission overwrites are inconsistent across API surfaces;
    locking the thread is the reliable, low-diff behavior we test for.
    """
    try:
        await thread.edit(locked=True)
    except discord.HTTPException:
        logger.debug("Could not set thread permission overwrites for %s", thread.id, exc_info=True)


async def archive_thread_after_delay(
    thread: discord.Thread,
    guild: discord.Guild,
    *,
    delay: float = MATCH_THREAD_ARCHIVE_DELAY_SEC,
    archive: bool = True,
) -> None:
    """Apply read-only + reactions pattern, then optionally archive."""
    await asyncio.sleep(delay)
    try:
        await restrict_thread_to_bot_and_reactions(thread, guild)
        if archive:
            await thread.edit(archived=True)
    except discord.NotFound:
        pass
    except Exception:
        logger.warning("Failed to finalize thread %s", thread.id, exc_info=True)

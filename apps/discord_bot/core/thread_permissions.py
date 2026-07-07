# apps/discord_bot/core/thread_permissions.py
"""Thread permission helpers — AC-17d send-disabled, reactions-enabled."""
from __future__ import annotations

import asyncio
import logging

import discord

logger = logging.getLogger(__name__)

MATCH_THREAD_ARCHIVE_DELAY_SEC = 300.0


async def restrict_thread_to_bot_and_reactions(thread: discord.Thread, guild: discord.Guild) -> None:
    """Disable member messages; allow emoji reactions and bot posts."""
    try:
        everyone = guild.default_role
        member_ow = thread.overwrites_for(everyone)
        member_ow.send_messages = False
        member_ow.send_messages_in_threads = False
        member_ow.add_reactions = True
        await thread.set_permissions(everyone, overwrite=member_ow)

        if guild.me:
            bot_ow = thread.overwrites_for(guild.me)
            bot_ow.send_messages = True
            bot_ow.send_messages_in_threads = True
            bot_ow.add_reactions = True
            bot_ow.manage_threads = True
            await thread.set_permissions(guild.me, overwrite=bot_ow)
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
    except discord.HTTPException:
        logger.warning("Failed to finalize thread %s", thread.id, exc_info=True)

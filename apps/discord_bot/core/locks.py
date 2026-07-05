# apps/discord_bot/core/locks.py
import asyncio
import logging

logger = logging.getLogger(__name__)

# Dictionary of asyncio.Locks mapped to guild_id
_guild_thread_locks: dict[int, asyncio.Lock] = {}
_lock = asyncio.Lock()

async def get_guild_thread_lock(guild_id: int) -> asyncio.Lock:
    """
    Returns a thread-safe Lock for a specific guild_id.
    Guards checking, creating, and updating of the League Journal thread.
    """
    async with _lock:
        if guild_id not in _guild_thread_locks:
            _guild_thread_locks[guild_id] = asyncio.Lock()
            logger.info(f"Initialized new asyncio.Lock for guild {guild_id}")
        return _guild_thread_locks[guild_id]

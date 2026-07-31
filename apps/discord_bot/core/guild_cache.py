# apps/discord_bot/core/guild_cache.py
"""Short-TTL guild_config reads (050 US6 Tier 2)."""
from __future__ import annotations

from typing import Any

from apps.discord_bot.core.cache import default_cache

DEFAULT_TTL_SECONDS = 600.0  # 10m within 5–15m band


def guild_config_key(guild_id: int) -> str:
    return f"guild:{int(guild_id)}:config"


def get_cached_guild_config(guild_id: int) -> dict | None:
    val = default_cache().get(guild_config_key(guild_id))
    return val if isinstance(val, dict) else None


def set_cached_guild_config(
    guild_id: int, row: dict, *, ttl_seconds: float = DEFAULT_TTL_SECONDS
) -> None:
    default_cache().set(guild_config_key(guild_id), row, ttl_seconds)


def invalidate_guild_config(guild_id: int) -> None:
    default_cache().delete(guild_config_key(guild_id))


async def load_guild_config(
    db: Any,
    guild_id: int,
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
) -> dict | None:
    """Read-only guild_config with TTL cache. Does not insert missing rows."""
    cached = get_cached_guild_config(guild_id)
    if cached is not None:
        return cached
    res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
    row = res.data if res else None
    if isinstance(row, dict):
        set_cached_guild_config(guild_id, row, ttl_seconds=ttl_seconds)
    return row

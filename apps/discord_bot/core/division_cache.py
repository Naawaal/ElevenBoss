# apps/discord_bot/core/division_cache.py
"""Process-local TTL cache for global_divisions ladder rows (US-44 HP-4).

Non-priced reference data — process TTL OK under multi-instance (US-43 FR-012).
"""
from __future__ import annotations

from typing import Any

from apps.discord_bot.core import config_cache

CACHE_KEY = "cfg:global_divisions:rows"
DEFAULT_TTL_SECONDS = 600.0


async def load_global_divisions(db: Any, *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> list[dict]:
    cached = config_cache.get(CACHE_KEY)
    if cached is not None:
        return list(cached)
    res = await db.table("global_divisions").select("*").order("min_lp").execute()
    rows = list(res.data or [])
    config_cache.set(CACHE_KEY, rows, ttl_seconds=ttl_seconds)
    return rows


def invalidate_global_divisions() -> None:
    config_cache.invalidate(CACHE_KEY)

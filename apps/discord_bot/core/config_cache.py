# apps/discord_bot/core/config_cache.py
"""Process-local TTL cache for game_config keys (US-43 Phase 1 / 050 US6).

Thin adapter over ``CacheBackend`` (default: memory). Multi-instance needs
shared/active invalidation for economy-priced keys (FR-012).
"""
from __future__ import annotations

from typing import Any

from apps.discord_bot.core.cache import default_cache

DEFAULT_TTL_SECONDS = 300.0

_backend = default_cache()


def cache_key(config_key: str) -> str:
    return f"cfg:{config_key}"


def get(key: str) -> Any | None:
    """Return cached value or None on miss/expiry. Key should already be namespaced."""
    return _backend.get(key)


def set(key: str, value: Any, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
    _backend.set(key, value, ttl_seconds)


def invalidate(key: str) -> None:
    _backend.delete(key)


def invalidate_prefix(prefix: str) -> None:
    _backend.delete_prefix(prefix)


def clear() -> None:
    _backend.clear()


def stats() -> dict[str, int]:
    raw = _backend.stats()
    return {
        "hits": int(raw["hits"]),
        "misses": int(raw["misses"]),
        "size": int(raw.get("size", raw.get("entries", 0))),
    }


def reset_stats() -> None:
    _backend.reset_stats()

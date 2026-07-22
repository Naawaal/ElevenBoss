# apps/discord_bot/core/config_cache.py
"""Process-local TTL cache for game_config keys (US-43 Phase 1).

ponytail: single-process dict — multi-instance must use shared/active invalidation
for economy-priced keys (FR-012). Upgrade path: shared backend behind same API
(``get``/``set``/``invalidate``) without changing call sites — e.g. Redis adapter
selected at bot startup when multi-instance is enabled.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

DEFAULT_TTL_SECONDS = 300.0

_lock = Lock()
_store: dict[str, tuple[Any, float]] = {}
_hits = 0
_misses = 0


def cache_key(config_key: str) -> str:
    return f"cfg:{config_key}"


def get(key: str) -> Any | None:
    """Return cached value or None on miss/expiry. Key should already be namespaced."""
    global _hits, _misses
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry is None:
            _misses += 1
            return None
        value, expires_at = entry
        if expires_at <= now:
            del _store[key]
            _misses += 1
            return None
        _hits += 1
        return value


def set(key: str, value: Any, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
    with _lock:
        _store[key] = (value, time.monotonic() + max(0.0, float(ttl_seconds)))


def invalidate(key: str) -> None:
    with _lock:
        _store.pop(key, None)


def invalidate_prefix(prefix: str) -> None:
    with _lock:
        doomed = [k for k in _store if k.startswith(prefix)]
        for k in doomed:
            del _store[k]


def clear() -> None:
    with _lock:
        _store.clear()


def stats() -> dict[str, int]:
    with _lock:
        return {"hits": _hits, "misses": _misses, "size": len(_store)}


def reset_stats() -> None:
    global _hits, _misses
    with _lock:
        _hits = 0
        _misses = 0

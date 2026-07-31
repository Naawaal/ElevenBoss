# apps/discord_bot/core/cache/memory.py
"""In-process TTL cache with per-key single-flight for async factories."""
from __future__ import annotations

import asyncio
import time
from threading import Lock
from typing import Any, Awaitable, Callable


class MemoryCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[str, tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
        self._flight_lock = asyncio.Lock()
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if expires_at <= now:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + max(0.0, float(ttl_seconds)))

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            doomed = [k for k in self._store if k.startswith(prefix)]
            for k in doomed:
                del self._store[k]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            hits = self._hits
            misses = self._misses
            size = len(self._store)
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "size": size,
            "entries": size,
            "hit_rate": (hits / total) if total else 0.0,
        }

    async def get_or_set(
        self,
        key: str,
        ttl_seconds: float,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        hit = self.get(key)
        if hit is not None:
            return hit

        async with self._flight_lock:
            hit = self.get(key)
            if hit is not None:
                return hit
            existing = self._inflight.get(key)
            if existing is not None:
                fut = existing
                waiter = True
            else:
                fut = asyncio.get_running_loop().create_future()
                self._inflight[key] = fut
                waiter = False

        if waiter:
            return await fut

        try:
            value = await factory()
            self.set(key, value, ttl_seconds)
            if not fut.done():
                fut.set_result(value)
            return value
        except Exception as exc:
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            async with self._flight_lock:
                self._inflight.pop(key, None)


_DEFAULT = MemoryCache()


def default_cache() -> MemoryCache:
    return _DEFAULT

# apps/discord_bot/core/cache/backend.py
"""CacheBackend protocol (050 US6 — process-local now, shared later)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: float) -> None: ...

    def delete(self, key: str) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...

    async def get_or_set(
        self,
        key: str,
        ttl_seconds: float,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any: ...

    def stats(self) -> dict[str, int | float]: ...

    def clear(self) -> None: ...

    def reset_stats(self) -> None: ...

"""CacheBackend memory + single-flight tests (050 US6)."""
from __future__ import annotations

import asyncio

import pytest

from apps.discord_bot.core.cache.memory import MemoryCache


@pytest.mark.asyncio
async def test_ttl_expiry() -> None:
    cache = MemoryCache()
    cache.set("k", "v", ttl_seconds=0.05)
    assert cache.get("k") == "v"
    await asyncio.sleep(0.08)
    assert cache.get("k") is None


@pytest.mark.asyncio
async def test_delete_prefix() -> None:
    cache = MemoryCache()
    cache.set("cfg:a", 1, 60)
    cache.set("cfg:b", 2, 60)
    cache.set("guild:1:config", 3, 60)
    cache.delete_prefix("cfg:")
    assert cache.get("cfg:a") is None
    assert cache.get("cfg:b") is None
    assert cache.get("guild:1:config") == 3


@pytest.mark.asyncio
async def test_get_or_set_single_flight() -> None:
    cache = MemoryCache()
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "payload"

    results = await asyncio.gather(
        cache.get_or_set("sf", 60, factory),
        cache.get_or_set("sf", 60, factory),
        cache.get_or_set("sf", 60, factory),
    )
    assert results == ["payload", "payload", "payload"]
    assert calls == 1
    assert cache.get("sf") == "payload"

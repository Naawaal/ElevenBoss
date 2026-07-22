# tests/test_config_cache.py
"""US-43 process-local config cache."""
from __future__ import annotations

import time

from apps.discord_bot.core import config_cache


def setup_function() -> None:
    config_cache.clear()
    config_cache.reset_stats()


def test_set_get_and_hit_miss() -> None:
    ck = config_cache.cache_key("drill_basic_energy")
    assert config_cache.get(ck) is None
    config_cache.set(ck, 10, ttl_seconds=60)
    assert config_cache.get(ck) == 10
    stats = config_cache.stats()
    assert stats["misses"] >= 1
    assert stats["hits"] >= 1


def test_ttl_expiry() -> None:
    ck = config_cache.cache_key("tmp")
    config_cache.set(ck, 1, ttl_seconds=0.05)
    assert config_cache.get(ck) == 1
    time.sleep(0.08)
    assert config_cache.get(ck) is None


def test_invalidate_and_prefix() -> None:
    a = config_cache.cache_key("a")
    b = config_cache.cache_key("b")
    config_cache.set(a, 1)
    config_cache.set(b, 2)
    config_cache.invalidate(a)
    assert config_cache.get(a) is None
    assert config_cache.get(b) == 2
    config_cache.invalidate_prefix("cfg:")
    assert config_cache.get(b) is None


def test_invalidate_game_config_priced_keys() -> None:
    from apps.discord_bot.core.economy_rpc import (
        invalidate_game_config,
        invalidate_priced_game_config,
    )

    ck = config_cache.cache_key("int:drill_basic_energy:5")
    config_cache.set(ck, 5)
    invalidate_game_config("drill_basic_energy")
    assert config_cache.get(ck) is None

    priced = config_cache.cache_key("num:energy_regen_per_min:0.25")
    other = config_cache.cache_key("int:drill_advanced_min_level:10")
    config_cache.set(priced, 0.25)
    config_cache.set(other, 10)
    invalidate_priced_game_config()
    assert config_cache.get(priced) is None
    assert config_cache.get(other) == 10


def test_training_drills_warm_cache_zero_config_rpc_contract() -> None:
    """After warm fill of HP-1 drill keys, further gets must not miss."""
    keys = [
        "drill_advanced_min_level",
        "drill_basic_energy",
        "drill_advanced_energy",
        "drill_basic_xp",
        "drill_advanced_xp",
    ]
    for k in keys:
        config_cache.set(config_cache.cache_key(f"int:{k}:0"), 1, ttl_seconds=300)
    config_cache.reset_stats()
    for k in keys:
        assert config_cache.get(config_cache.cache_key(f"int:{k}:0")) == 1
    stats = config_cache.stats()
    assert stats["misses"] == 0
    assert stats["hits"] == len(keys)

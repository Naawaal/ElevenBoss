# tests/test_hub_hot_path_wave2.py
"""US-44 hub hot-path wave 2 contracts (HP-4…HP-6)."""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.discord_bot.core import config_cache, division_cache

ROOT = Path(__file__).resolve().parents[1]


def setup_function() -> None:
    config_cache.clear()
    config_cache.reset_stats()


def test_squad_fetch_uses_gather_and_count() -> None:
    text = (ROOT / "apps/discord_bot/cogs/squad_cog.py").read_text(encoding="utf-8")
    assert "asyncio.gather" in text
    assert 'count="exact"' in text
    assert "hub_timer(\"squad\")" in text or "hub_timer('squad')" in text


def test_league_hub_keeps_auto_sim_and_batches_join_limits() -> None:
    text = (ROOT / "apps/discord_bot/cogs/league_cog.py").read_text(encoding="utf-8")
    assert "auto_sim_expired_fixtures" in text
    assert "get_game_config_many" in text
    assert "_load_league_and_open_season" in text
    assert "hub_timer(\"league_hub\")" in text or "hub_timer('league_hub')" in text
    assert "use_v1_regs" in text


def test_profile_uses_division_cache_and_gather() -> None:
    text = (ROOT / "apps/discord_bot/cogs/profile_cog.py").read_text(encoding="utf-8")
    assert "load_global_divisions" in text
    assert "asyncio.gather" in text
    assert "hub_timer(\"profile\")" in text or "hub_timer('profile')" in text


@pytest.mark.asyncio
async def test_division_cache_hit_skips_second_query() -> None:
    calls = {"n": 0}

    class _Res:
        data = [{"name": "Bronze III", "min_lp": 0}]

    class _Query:
        def select(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        async def execute(self):
            calls["n"] += 1
            return _Res()

    class _Db:
        def table(self, name: str):
            assert name == "global_divisions"
            return _Query()

    db = _Db()
    a = await division_cache.load_global_divisions(db)
    b = await division_cache.load_global_divisions(db)
    assert a == b
    assert calls["n"] == 1
    division_cache.invalidate_global_divisions()
    await division_cache.load_global_divisions(db)
    assert calls["n"] == 2


def test_integrity_guard_doc_exists() -> None:
    text = (
        ROOT / "specs/039-hub-hot-path-wave2/contracts/integrity-guards.md"
    ).read_text(encoding="utf-8")
    assert "auto_sim" in text.lower() or "Auto-sim" in text

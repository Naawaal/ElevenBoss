# tests/test_nss_v3_dual_run_pin.py
"""US4: in-flight pins; flags only affect new runs."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.discord_bot.core.match_runs import (
    ENGINE_NSS_V2,
    ENGINE_NSS_V3,
    create_ephemeral_run,
    resolve_engine_version,
)


@pytest.mark.asyncio
async def test_resolve_engine_defaults_v2(monkeypatch):
    async def _cfg(_db, key, default=0):
        return 0

    monkeypatch.setattr(
        "apps.discord_bot.core.economy_rpc.get_game_config_int",
        _cfg,
    )
    ev, ssv = await resolve_engine_version(MagicMock(), "bot")
    assert ev == ENGINE_NSS_V2
    assert ssv == 1


@pytest.mark.asyncio
async def test_resolve_engine_flag_enables_v3(monkeypatch):
    async def _cfg(_db, key, default=0):
        return 1 if key == "match_engine_v3_league" else 0

    monkeypatch.setattr(
        "apps.discord_bot.core.economy_rpc.get_game_config_int",
        _cfg,
    )
    ev, ssv = await resolve_engine_version(MagicMock(), "league")
    assert ev == ENGINE_NSS_V3
    assert ssv == 2
    ev_bot, _ = await resolve_engine_version(MagicMock(), "bot")
    assert ev_bot == ENGINE_NSS_V2


@pytest.mark.asyncio
async def test_resolve_bot_on_league_off(monkeypatch):
    """Soak cutover: bot V3 does not force league V3."""

    async def _cfg(_db, key, default=0):
        return 1 if key == "match_engine_v3_bot" else 0

    monkeypatch.setattr(
        "apps.discord_bot.core.economy_rpc.get_game_config_int",
        _cfg,
    )
    ev_bot, ssv = await resolve_engine_version(MagicMock(), "bot")
    assert ev_bot == ENGINE_NSS_V3
    assert ssv == 2
    ev_league, _ = await resolve_engine_version(MagicMock(), "league")
    assert ev_league == ENGINE_NSS_V2
    ev_friendly, _ = await resolve_engine_version(MagicMock(), "friendly")
    assert ev_friendly == ENGINE_NSS_V2


@pytest.mark.asyncio
async def test_create_ephemeral_run_pins_version(monkeypatch):
    inserted: dict = {}

    class Table:
        def insert(self, payload):
            inserted.clear()
            inserted.update(payload)
            m = MagicMock()
            m.execute = AsyncMock(return_value=MagicMock(data=[dict(payload)]))
            return m

    class DB:
        def table(self, name):
            assert name == "match_runs"
            return Table()

    async def _cfg(_db, key, default=0):
        return 1

    monkeypatch.setattr(
        "apps.discord_bot.core.economy_rpc.get_game_config_int",
        _cfg,
    )
    row = await create_ephemeral_run(
        DB(),
        run_type="bot",
        active_discord_id=1,
        home_discord_id=1,
        away_discord_id=None,
        sim_seed=42,
        guild_id=1,
        thread_id=2,
    )
    assert row["engine_version"] == ENGINE_NSS_V3
    assert inserted["engine_version"] == ENGINE_NSS_V3
    row2 = await create_ephemeral_run(
        DB(),
        run_type="bot",
        active_discord_id=1,
        home_discord_id=1,
        away_discord_id=None,
        sim_seed=42,
        guild_id=1,
        thread_id=2,
        engine_version=ENGINE_NSS_V2,
        simulation_schema_version=1,
    )
    assert row2["engine_version"] == ENGINE_NSS_V2

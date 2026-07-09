# tests/test_match_loop_hardening.py
"""US-29 — bot match XP and economy helpers."""
from __future__ import annotations

import pytest

from apps.discord_bot.core.economy_rpc import (
    compute_bot_match_coins,
    get_match_energy_cost,
    match_energy_cost,
)
from apps.discord_bot.core.match_xp import build_process_match_result_rpc


def test_bot_match_energy_cost_v2() -> None:
    assert match_energy_cost("bot", v2=True) == 20
    assert match_energy_cost("league", v2=True) == 10


class _MockRpc:
    def __init__(self, data):
        self.data = data

    async def execute(self):
        return self


class _MockDb:
    def __init__(self, value):
        self._value = value

    def rpc(self, name, payload):
        assert name == "get_game_config_int"
        return _MockRpc(self._value)


@pytest.mark.asyncio
async def test_get_match_energy_cost_reads_game_config() -> None:
    db = _MockDb(15)
    assert await get_match_energy_cost(db, "bot", v2=True) == 15


@pytest.mark.asyncio
async def test_get_match_energy_cost_falls_back_on_unknown_type() -> None:
    db = _MockDb(99)
    assert await get_match_energy_cost(db, "unknown", v2=True) == 20


def test_bot_match_coins_use_config_not_inline_loss() -> None:
    win = compute_bot_match_coins("win", division_win_coins=100, v2=True)
    draw = compute_bot_match_coins("draw", division_win_coins=100, v2=True)
    loss = compute_bot_match_coins("loss", division_win_coins=100, v2=True)
    assert win > draw >= loss
    assert loss != 15  # old hardcoded consolation


def test_build_process_match_result_rpc_bot_type() -> None:
    cards = [{"id": "aaa", "name": "Striker"}]
    payload = build_process_match_result_rpc(
        cards,
        result="win",
        match_type="bot",
        motm_name="Striker",
        key_events=[],
        club_name="FC Test",
        team_rating=7.0,
    )
    assert payload["p_xp_amounts"]
    assert payload["p_card_ratings"] == [7.0]

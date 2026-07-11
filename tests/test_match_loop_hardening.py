# tests/test_match_loop_hardening.py
"""US-29 — bot match XP and economy helpers; match XP + energy regen fixes."""
from __future__ import annotations

import pytest

from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.core.economy_rpc import (
    compute_bot_match_coins,
    format_action_energy_status,
    get_match_energy_cost,
    match_energy_cost,
    minutes_to_full_action_energy,
)
from apps.discord_bot.core.match_xp import (
    build_process_match_result_rpc,
    hydrate_cards_for_match_xp,
)


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


class _HydrateTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._ids: list | None = None

    def select(self, _cols: str):
        return self

    def in_(self, _col: str, ids: list):
        self._ids = ids
        return self

    async def execute(self):
        wanted = {str(i) for i in (self._ids or [])}
        return _MockRpc([r for r in self._rows if str(r["id"]) in wanted])


class _HydrateDb:
    def __init__(self, rows: list[dict]):
        self._table = _HydrateTable(rows)

    def table(self, name: str):
        assert name == "player_cards"
        return self._table


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
    assert all(x > 0 for x in payload["p_xp_amounts"])


def test_build_process_match_result_rpc_hydrated_league_cards() -> None:
    cards = [
        {"id": "c1", "name": "Keeper", "age": 22},
        {"id": "c2", "name": "Striker", "date_of_birth": "2000-01-15"},
    ]
    payload = build_process_match_result_rpc(
        cards,
        result="draw",
        match_type="league",
        motm_name="Striker",
        key_events=[],
        club_name="FC Test",
        team_rating=6.5,
    )
    assert payload["p_card_ids"] == ["c1", "c2"]
    assert len(payload["p_xp_amounts"]) == 2


def test_build_process_match_result_rpc_id_only_cards_raise() -> None:
    with pytest.raises(KeyError):
        build_process_match_result_rpc(
            [{"id": "orphan"}],
            result="win",
            match_type="league",
            motm_name="X",
            key_events=[],
            club_name="FC Test",
            team_rating=7.0,
        )


@pytest.mark.asyncio
async def test_hydrate_cards_for_match_xp_preserves_order() -> None:
    db = _HydrateDb(
        [
            {"id": "b", "name": "B", "age": 20},
            {"id": "a", "name": "A", "age": 21},
        ]
    )
    rows = await hydrate_cards_for_match_xp(db, ["a", "b", "missing"])
    assert [r["name"] for r in rows] == ["A", "B"]
    payload = build_process_match_result_rpc(
        rows,
        result="win",
        match_type="bot",
        motm_name="A",
        key_events=[],
        club_name="FC Test",
        team_rating=7.0,
    )
    assert payload["p_xp_amounts"]


def test_minutes_to_full_action_energy_is_four_min_rate() -> None:
    assert minutes_to_full_action_energy(0, 100) == 400
    assert minutes_to_full_action_energy(0, 100) != 600
    status = format_action_energy_status(0, 100)
    assert "6h 40m" in status


def test_bot_and_league_reward_helpers_use_xp_match_types() -> None:
    """Friendly is sandbox — only bot/league call apply_match_xp_if_needed."""
    import inspect

    from apps.discord_bot.core import league_rewards, match_rewards

    bot_src = inspect.getsource(match_rewards.apply_bot_match_rewards)
    league_src = inspect.getsource(league_rewards.apply_league_human_rewards)
    assert 'match_type="bot"' in bot_src
    assert 'match_type="league"' in league_src
    assert "friendly" not in bot_src
    assert "friendly" not in league_src


def test_match_xp_failure_maps_to_friendly_copy() -> None:
    msg = api_error_message(RuntimeError("Match XP could not be applied")).lower()
    assert "player xp could not be saved" in msg

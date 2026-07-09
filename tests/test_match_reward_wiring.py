# tests/test_match_reward_wiring.py
"""Integration-style tests for match reward wiring (US-29 / audit remediation)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.discord_bot.core.league_rewards import (
    apply_league_human_rewards,
    check_matchday_milestone,
)
from apps.discord_bot.core.match_rewards import apply_bot_match_rewards


class _Chain:
    def __init__(self, db: "_MockDb", table: str) -> None:
        self._db = db
        self._table = table
        self._filters: dict = {}

    def select(self, *_cols: str) -> "_Chain":
        return self

    def eq(self, key: str, val: object) -> "_Chain":
        self._filters[key] = val
        return self

    def insert(self, row: dict) -> "_Chain":
        self._db.pending_insert = row
        return self

    def update(self, _row: dict) -> "_Chain":
        return self

    def maybe_single(self) -> "_Chain":
        return self

    async def execute(self) -> MagicMock:
        if self._table == "match_history" and self._db.pending_insert is not None:
            row = {**self._db.pending_insert, "id": "hist-1"}
            self._db.pending_insert = None
            return MagicMock(data=[row])
        return MagicMock(data=None)


class _MockDb:
    def __init__(self) -> None:
        self.rpc_calls: list[tuple[str, dict]] = []
        self.insert_row: dict | None = {"id": "hist-1", "coins_earned": 50, "points_earned": 3}
        self.pending_insert: dict | None = None
        self.config_ints: dict[str, int] = {
            "league_milestone_pts_threshold": 6,
            "league_milestone_bonus_coins": 150,
        }

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)

    def rpc(self, name: str, payload: dict) -> "_Rpc":
        return _Rpc(self, name, payload)


class _Rpc:
    def __init__(self, db: _MockDb, name: str, payload: dict) -> None:
        self._db = db
        self._name = name
        self._payload = payload

    async def execute(self) -> MagicMock:
        self._db.rpc_calls.append((self._name, self._payload))
        if self._name == "get_game_config":
            key = self._payload.get("p_key", "")
            if key == "economy_v2_enabled":
                return MagicMock(data=True)
            if key in self._db.config_ints:
                return MagicMock(data=self._db.config_ints[key])
            return MagicMock(data=None)
        if self._name == "get_game_config_int":
            return MagicMock(data=self._payload.get("p_default", 20))
        if self._name == "sync_action_energy":
            return MagicMock(data={"action_energy": 100})
        if self._name == "upsert_matchday_milestone_points":
            return MagicMock(data={"points_earned": 6, "milestone_claimed": False})
        return MagicMock(data={})


@pytest.mark.asyncio
async def test_apply_bot_match_rewards_calls_career_stats_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _MockDb()

    async def _noop_xp(*_a, **_k):
        return None

    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.apply_match_xp_if_needed",
        _noop_xp,
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.fetch_match_reward_row",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.apply_match_economy",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.sync_action_energy",
        AsyncMock(return_value={"action_energy": 100}),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.economy_v2_enabled",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.get_match_energy_cost",
        AsyncMock(return_value=20),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.compute_bot_match_coins",
        lambda *_a, **_k: 75,
    )

    coins = await apply_bot_match_rewards(
        db,
        player_id=1,
        player_row={
            "league_points": 10,
            "global_lp": 100,
            "goal_difference": 0,
            "matches_played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
        },
        result_str="win",
        cards=[{"id": "c1", "name": "Striker"}],
        club_name="FC Test",
        team_rating=7.0,
        opponent_rating=6.0,
        goals_for=2,
        goals_against=1,
        points_earned=3,
        lp_change=10,
        division_win_coins=100,
        run_id="run-abc",
        motm_name="Striker",
        key_events=[],
    )

    assert coins == 75
    career_calls = [c for c in db.rpc_calls if c[0] == "increment_match_career_stats"]
    assert len(career_calls) == 1
    assert career_calls[0][1]["p_lp_change"] == 10
    assert career_calls[0][1]["p_goal_diff_delta"] == 1


@pytest.mark.asyncio
async def test_apply_bot_match_rewards_skips_when_xp_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _MockDb()
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.fetch_match_reward_row",
        AsyncMock(return_value={"id": "h1", "coins_earned": 42, "xp_applied_at": "2026-01-01T00:00:00Z"}),
    )
    economy = AsyncMock()
    monkeypatch.setattr("apps.discord_bot.core.match_rewards.apply_match_economy", economy)

    coins = await apply_bot_match_rewards(
        db,
        player_id=1,
        player_row={},
        result_str="win",
        cards=[],
        club_name="FC",
        team_rating=7.0,
        opponent_rating=6.0,
        goals_for=1,
        goals_against=0,
        points_earned=3,
        lp_change=5,
        division_win_coins=100,
        run_id="run-abc",
        motm_name="",
        key_events=[],
    )

    assert coins == 42
    economy.assert_not_called()


@pytest.mark.asyncio
async def test_apply_league_human_rewards_calls_league_career_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _MockDb()

    async def _noop_xp(*_a, **_k):
        return None

    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.apply_match_xp_if_needed",
        _noop_xp,
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.fetch_match_reward_row",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.apply_match_economy",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.economy_v2_enabled",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.get_match_energy_cost",
        AsyncMock(return_value=10),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.sync_action_energy",
        AsyncMock(return_value={"action_energy": 50}),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.league_rewards.compute_league_match_coins",
        lambda *_a, **_k: 60,
    )

    coins, pts = await apply_league_human_rewards(
        db,
        player_id=2,
        player_row={"matches_played": 1, "wins": 0, "draws": 0, "losses": 1, "division": "Grassroots"},
        result_str="win",
        fixture_id="fix-1",
        run_id="run-league",
        cards=[{"id": "c1", "name": "A"}],
        club_name="United",
        team_rating=6.5,
        motm_name="A",
        key_events=[],
        goals_for=2,
        goals_against=0,
        deduct_energy=True,
    )

    assert coins == 60
    assert pts == 3
    league_calls = [c for c in db.rpc_calls if c[0] == "increment_league_career_stats"]
    assert len(league_calls) == 1
    assert league_calls[0][1]["p_result"] == "win"


@pytest.mark.asyncio
async def test_check_matchday_milestone_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _MockDb()
    monkeypatch.setattr(
        "apps.discord_bot.core.economy_rpc.apply_club_economy",
        AsyncMock(),
    )

    bonus = await check_matchday_milestone(
        db,
        player_id=9,
        season_id="season-1",
        matchday=2,
        points_earned=3,
    )

    assert bonus == 150
    upsert_calls = [c for c in db.rpc_calls if c[0] == "upsert_matchday_milestone_points"]
    assert len(upsert_calls) == 1
    assert upsert_calls[0][1]["p_points_delta"] == 3

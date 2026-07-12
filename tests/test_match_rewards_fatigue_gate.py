# tests/test_match_rewards_fatigue_gate.py
"""Fatigue gate separate from xp_applied_at (014)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apps.discord_bot.core.match_rewards import apply_bot_match_rewards


@pytest.mark.asyncio
async def test_xp_applied_still_runs_pending_fitness(monkeypatch: pytest.MonkeyPatch) -> None:
    fitness = AsyncMock(return_value={"injuries": {"overflow": []}})
    mark = AsyncMock()
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.fetch_match_reward_row",
        AsyncMock(
            return_value={
                "id": "h1",
                "coins_earned": 42,
                "xp_applied_at": "2026-01-01T00:00:00Z",
                "fatigue_applied_at": None,
            }
        ),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.apply_match_xp_if_needed",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.apply_post_match_fitness",
        fitness,
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.mark_match_fatigue_applied",
        mark,
    )
    economy = AsyncMock()
    monkeypatch.setattr("apps.discord_bot.core.match_rewards.apply_match_economy", economy)
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.economy_v2_enabled",
        AsyncMock(return_value=True),
    )

    coins, summary = await apply_bot_match_rewards(
        AsyncMock(),
        player_id=1,
        player_row={},
        result_str="win",
        cards=[{"id": "c1", "phy": 50}],
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
        bench_ids=["b1", "b2"],
    )

    assert coins == 42
    economy.assert_not_called()
    fitness.assert_awaited_once()
    mark.assert_awaited_once()
    assert mark.await_args.args[1] == "h1"
    assert summary["ok"] is True
    assert summary["bench_count"] == 2
    assert "Bench rest" in (summary.get("line") or "")


@pytest.mark.asyncio
async def test_both_gates_skip_fitness(monkeypatch: pytest.MonkeyPatch) -> None:
    fitness = AsyncMock()
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.fetch_match_reward_row",
        AsyncMock(
            return_value={
                "id": "h1",
                "coins_earned": 42,
                "xp_applied_at": "2026-01-01T00:00:00Z",
                "fatigue_applied_at": "2026-01-01T00:01:00Z",
            }
        ),
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.match_rewards.apply_post_match_fitness",
        fitness,
    )
    economy = AsyncMock()
    monkeypatch.setattr("apps.discord_bot.core.match_rewards.apply_match_economy", economy)

    coins, summary = await apply_bot_match_rewards(
        AsyncMock(),
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
    fitness.assert_not_called()
    assert summary.get("already_applied") is True

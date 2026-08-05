# tests/test_match_concurrency_integrity.py
"""Unit and integration tests for Match Concurrency & Squad Locking Integrity (Feature 056)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from match_engine import MatchPlayerCard

from apps.discord_bot.core.match_runs import (
    build_ephemeral_match_snapshot,
    complete_run,
    squads_from_snapshot,
)
from apps.discord_bot.middleware.match_lock import (
    assert_not_in_match,
    is_in_match,
    reject_if_in_match,
)


def test_build_ephemeral_match_snapshot() -> None:
    card1 = MatchPlayerCard(name="Player A", position="FWD", overall=80)
    card2 = MatchPlayerCard(name="Player B", position="DEF", overall=75)

    snap = build_ephemeral_match_snapshot(
        home_name="Home FC",
        away_name="Away FC",
        home_squad=[card1],
        away_squad=[card2],
        home_cards=[{"id": "card-1"}],
        away_cards=[{"id": "card-2"}],
        home_formation="4-3-3",
        away_formation="4-4-2",
    )

    assert snap["home_name"] == "Home FC"
    assert snap["away_name"] == "Away FC"
    assert snap["home_formation"] == "4-3-3"
    assert snap["away_formation"] == "4-4-2"
    assert len(snap["home_squad"]) == 1
    assert len(snap["away_squad"]) == 1
    assert snap["home_card_ids"] == ["card-1"]
    assert snap["away_card_ids"] == ["card-2"]

    home_cards, away_cards = squads_from_snapshot(snap)
    assert len(home_cards) == 1
    assert home_cards[0].name == "Player A"
    assert len(away_cards) == 1
    assert away_cards[0].name == "Player B"


@pytest.mark.asyncio
async def test_is_in_match_true() -> None:
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_single = MagicMock()
    mock_exec = AsyncMock()

    mock_db.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.maybe_single.return_value = mock_single
    mock_single.execute = mock_exec
    mock_exec.return_value = MagicMock(data={"discord_id": 123456})

    locked = await is_in_match(mock_db, 123456)
    assert locked is True


@pytest.mark.asyncio
async def test_assert_not_in_match_locked() -> None:
    mock_db = MagicMock()
    with patch("apps.discord_bot.middleware.match_lock.is_in_match", AsyncMock(return_value=True)):
        msg = await assert_not_in_match(mock_db, 123456)
        assert msg is not None
        assert "locked in an active match" in msg


@pytest.mark.asyncio
async def test_reject_if_in_match_available() -> None:
    mock_interaction = AsyncMock()
    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_exec = AsyncMock()

    mock_db.rpc.return_value = mock_rpc
    mock_rpc.execute = mock_exec
    mock_exec.return_value = MagicMock(data={"available": True})

    rejected = await reject_if_in_match(mock_interaction, mock_db, 123456)
    assert rejected is False
    assert not mock_interaction.response.send_message.called


@pytest.mark.asyncio
async def test_reject_if_in_match_locked() -> None:
    mock_interaction = AsyncMock()
    mock_interaction.response.is_done = MagicMock(return_value=False)
    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_exec = AsyncMock()

    mock_db.rpc.return_value = mock_rpc
    mock_rpc.execute = mock_exec
    mock_exec.return_value = MagicMock(
        data={"available": False, "message": "manager_in_active_match"}
    )

    rejected = await reject_if_in_match(mock_interaction, mock_db, 123456)
    assert rejected is True
    assert mock_interaction.response.send_message.called


@pytest.mark.asyncio
async def test_complete_run_releases_locks() -> None:
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_update = MagicMock()
    mock_delete = MagicMock()
    mock_eq1 = MagicMock()
    mock_eq2 = MagicMock()
    mock_exec_update = AsyncMock()
    mock_exec_delete = AsyncMock()

    mock_db.table.return_value = mock_table
    mock_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_eq1
    mock_eq1.execute = mock_exec_update

    mock_table.delete.return_value = mock_delete
    mock_delete.eq.return_value = mock_eq2
    mock_eq2.execute = mock_exec_delete

    await complete_run(mock_db, "run-12345", home_score=2, away_score=1)
    assert mock_table.update.called
    assert mock_table.delete.called

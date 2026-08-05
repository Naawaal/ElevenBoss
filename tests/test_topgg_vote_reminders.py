# tests/test_topgg_vote_reminders.py
"""Unit and integration tests for Top.gg vote reminders (Feature 055)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.discord_bot.core.topgg_vote import (
    VoteCheckResult,
    topgg_vote_url,
    upsert_vote_reminder_window,
)
from apps.discord_bot.tasks.topgg_vote_reminder_job import (
    build_vote_reminder_embed,
    run_topgg_vote_reminders,
)


def test_build_vote_reminder_embed() -> None:
    embed = build_vote_reminder_embed()
    assert "Ready to vote again?" in (embed.title or "")
    assert "Top.gg" in (embed.description or "")
    assert embed.color is not None and embed.color.value == 0xF1C40F


def test_topgg_vote_url() -> None:
    url = topgg_vote_url(runtime_bot_id=123456789)
    assert "123456789" in url or "top.gg" in url


@pytest.mark.asyncio
async def test_upsert_vote_reminder_window_structure() -> None:
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_upsert = MagicMock()
    mock_exec = AsyncMock()

    mock_db.table.return_value = mock_table
    mock_table.upsert.return_value = mock_upsert
    mock_upsert.execute = mock_exec
    mock_exec.return_value = MagicMock(data=[{"discord_user_id": 999}])

    now = datetime.now(timezone.utc)
    res = await upsert_vote_reminder_window(
        mock_db,
        discord_user_id=999,
        last_vote_at=now,
        next_vote_at=now + timedelta(hours=12),
    )

    assert res is not None
    assert mock_table.upsert.called
    upsert_data = mock_table.upsert.call_args[0][0]
    assert upsert_data["discord_user_id"] == 999
    assert upsert_data["reminder_window_key"].startswith("999:")


@pytest.mark.asyncio
async def test_run_topgg_vote_reminders_no_rows() -> None:
    mock_bot = MagicMock()
    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_exec = AsyncMock()

    mock_db.rpc.return_value = mock_rpc
    mock_rpc.execute = mock_exec
    mock_exec.return_value = MagicMock(data=[])

    with patch("apps.discord_bot.tasks.topgg_vote_reminder_job.get_client", AsyncMock(return_value=mock_db)):
        await run_topgg_vote_reminders(mock_bot)

    assert mock_db.rpc.called


@pytest.mark.asyncio
async def test_run_topgg_vote_reminders_send_dm_success() -> None:
    mock_bot = MagicMock()
    mock_user = AsyncMock()
    mock_bot.get_user.return_value = mock_user

    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_exec_rpc = AsyncMock()

    mock_db.rpc.return_value = mock_rpc
    mock_rpc.execute = mock_exec_rpc
    mock_exec_rpc.return_value = MagicMock(
        data=[
            {
                "discord_user_id": 12345,
                "reminder_window_key": "12345:2026-08-05T12:00:00Z",
                "last_vote_at": "2026-08-05T00:00:00Z",
                "next_vote_at": "2026-08-05T12:00:00Z",
                "next_check_at": "2026-08-05T12:00:00Z",
                "check_failure_count": 0,
            }
        ]
    )

    mock_table = MagicMock()
    mock_update = MagicMock()
    mock_eq = MagicMock()
    mock_exec_update = AsyncMock()

    mock_db.table.return_value = mock_table
    mock_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_eq
    mock_eq.execute = mock_exec_update

    with (
        patch("apps.discord_bot.tasks.topgg_vote_reminder_job.get_client", AsyncMock(return_value=mock_db)),
        patch(
            "apps.discord_bot.tasks.topgg_vote_reminder_job.check_topgg_vote",
            AsyncMock(return_value=VoteCheckResult(status="not_voted")),
        ),
    ):
        await run_topgg_vote_reminders(mock_bot)

    assert mock_user.send.called
    assert mock_table.update.called
    update_data = mock_table.update.call_args[0][0]
    assert update_data["dm_status"] == "sent"
    assert update_data["fallback_pending"] is False


@pytest.mark.asyncio
async def test_maybe_send_pending_vote_notice_success() -> None:
    from apps.discord_bot.core.pending_notices import maybe_send_pending_vote_notice

    mock_interaction = AsyncMock()
    mock_interaction.user.id = 999
    mock_interaction.client.user.id = 12345
    mock_interaction.response.is_done = MagicMock(return_value=False)

    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq1 = MagicMock()
    mock_eq2 = MagicMock()
    mock_single = MagicMock()
    mock_exec_select = AsyncMock()

    mock_db.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq1
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.maybe_single.return_value = mock_single
    mock_single.execute = mock_exec_select
    mock_exec_select.return_value = MagicMock(
        data={
            "discord_user_id": 999,
            "fallback_pending": True,
            "next_vote_at": "2026-08-05T00:00:00Z",
        }
    )

    mock_update = MagicMock()
    mock_update_eq = MagicMock()
    mock_exec_update = AsyncMock()
    mock_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_update_eq
    mock_update_eq.execute = mock_exec_update

    sent = await maybe_send_pending_vote_notice(mock_interaction, mock_db)
    assert sent is True
    assert mock_interaction.response.send_message.called
    assert mock_table.update.called
    update_arg = mock_table.update.call_args[0][0]
    assert update_arg["fallback_pending"] is False


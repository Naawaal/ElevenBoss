# tests/test_topgg_vote.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.discord_bot.core.topgg_vote import (
    VoteCheckResult,
    check_topgg_vote,
    topgg_vote_url,
)


def _future_iso(hours: float = 6.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past_iso(hours: float = 6.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


@pytest.mark.asyncio
async def test_empty_token_returns_unavailable() -> None:
    result = await check_topgg_vote(discord_user_id=123, token="")
    assert result == VoteCheckResult(status="unavailable")


@pytest.mark.asyncio
async def test_active_vote_v1() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "votedAt": _past_iso(1),
        "nextVoteAt": _future_iso(6),
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.discord_bot.core.topgg_vote.httpx.AsyncClient", return_value=mock_client):
        result = await check_topgg_vote(discord_user_id=999, token="test-token")

    assert result.status == "voted"
    assert result.vote_at is not None
    assert result.next_vote_at is not None


@pytest.mark.asyncio
async def test_not_voted_404() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.discord_bot.core.topgg_vote.httpx.AsyncClient", return_value=mock_client):
        result = await check_topgg_vote(discord_user_id=999, token="test-token")

    assert result == VoteCheckResult(status="not_voted")


@pytest.mark.asyncio
async def test_server_error_unavailable() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 503

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.discord_bot.core.topgg_vote.httpx.AsyncClient", return_value=mock_client):
        result = await check_topgg_vote(discord_user_id=999, token="test-token")

    assert result == VoteCheckResult(status="unavailable")


@pytest.mark.asyncio
async def test_timeout_unavailable() -> None:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.discord_bot.core.topgg_vote.httpx.AsyncClient", return_value=mock_client):
        result = await check_topgg_vote(discord_user_id=999, token="test-token")

    assert result == VoteCheckResult(status="unavailable")


def test_topgg_vote_url_runtime_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOPGG_BOT_ID", raising=False)
    assert topgg_vote_url(runtime_bot_id=123456789) == "https://top.gg/bot/123456789/vote"


def test_topgg_vote_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOPGG_BOT_ID", "1521477038270189638")
    assert topgg_vote_url(runtime_bot_id=1523372906128871665) == (
        "https://top.gg/bot/1521477038270189638/vote"
    )

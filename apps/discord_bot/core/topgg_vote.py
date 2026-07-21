# apps/discord_bot/core/topgg_vote.py
"""Top.gg vote verification for Store free pack (025-topgg-vote-pack)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
logger = logging.getLogger(__name__)

TOPGG_V1_BASE = "https://top.gg/api/v1"
TOPGG_V0_BASE = "https://top.gg/api"
DEFAULT_TIMEOUT = 8.0


@dataclass(frozen=True)
class VoteCheckResult:
    status: Literal["voted", "not_voted", "unavailable"]
    vote_at: datetime | None = None
    next_vote_at: datetime | None = None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _active_vote_from_body(body: dict, now: datetime) -> VoteCheckResult | None:
    next_vote_at = _parse_iso(body.get("nextVoteAt") or body.get("next_vote_at"))
    vote_at = _parse_iso(
        body.get("votedAt")
        or body.get("voted_at")
        or body.get("createdAt")
        or body.get("created_at")
    )

    if next_vote_at is not None and next_vote_at <= now:
        return VoteCheckResult(status="not_voted")

    if next_vote_at is not None and next_vote_at > now:
        if vote_at is None:
            vote_at = now
        return VoteCheckResult(status="voted", vote_at=vote_at, next_vote_at=next_vote_at)

    if vote_at is not None and vote_at >= now - timedelta(hours=12):
        return VoteCheckResult(status="voted", vote_at=vote_at, next_vote_at=next_vote_at)

    return None


async def check_topgg_vote(
    *,
    discord_user_id: int,
    token: str,
    bot_id: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> VoteCheckResult:
    """Check whether a Discord user has an active Top.gg vote."""
    if not token or not token.strip():
        logger.warning("Top.gg vote check skipped — TOPGG_TOKEN not configured")
        return VoteCheckResult(status="unavailable")

    now = datetime.now(timezone.utc)
    headers = {"Authorization": f"Bearer {token.strip()}", "Accept": "application/json"}
    url = f"{TOPGG_V1_BASE}/projects/@me/votes/{discord_user_id}?source=discord"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 404:
                return VoteCheckResult(status="not_voted")

            if response.status_code == 401 and bot_id is not None:
                return await _check_topgg_vote_v0(
                    client=client,
                    bot_id=bot_id,
                    discord_user_id=discord_user_id,
                    token=token.strip(),
                    now=now,
                )

            if response.status_code >= 500 or response.status_code == 429:
                logger.warning("Top.gg vote check failed — HTTP %s", response.status_code)
                return VoteCheckResult(status="unavailable")

            if response.status_code != 200:
                logger.warning("Top.gg vote check unexpected status — HTTP %s", response.status_code)
                return VoteCheckResult(status="unavailable")

            body = response.json()
            if not isinstance(body, dict):
                return VoteCheckResult(status="unavailable")

            parsed = _active_vote_from_body(body, now)
            if parsed is not None:
                return parsed
            return VoteCheckResult(status="not_voted")

    except httpx.TimeoutException:
        logger.warning("Top.gg vote check timed out")
        return VoteCheckResult(status="unavailable")
    except httpx.HTTPError:
        logger.warning("Top.gg vote check HTTP error", exc_info=True)
        return VoteCheckResult(status="unavailable")


async def _check_topgg_vote_v0(
    *,
    client: httpx.AsyncClient,
    bot_id: int,
    discord_user_id: int,
    token: str,
    now: datetime,
) -> VoteCheckResult:
    """Legacy v0 fallback when v1 auth fails."""
    url = f"{TOPGG_V0_BASE}/bots/{bot_id}/check"
    response = await client.get(url, params={"userId": str(discord_user_id)}, headers={"Authorization": token})
    if response.status_code != 200:
        return VoteCheckResult(status="unavailable")
    body = response.json()
    if isinstance(body, dict) and body.get("voted") == 1:
        return VoteCheckResult(status="voted", vote_at=now)
    return VoteCheckResult(status="not_voted")


TOPGG_BOT_ID = 1521477038270189638


def resolve_topgg_bot_id(runtime_bot_id: int | None = None) -> int:
    """Top.gg listing bot ID — may differ from the running Discord application (dev vs prod)."""
    raw = os.environ.get("TOPGG_BOT_ID", "").strip()
    if raw:
        return int(raw)
    if runtime_bot_id is not None:
        return runtime_bot_id
    return TOPGG_BOT_ID


def topgg_vote_url(*, runtime_bot_id: int | None = None) -> str:
    return f"https://top.gg/bot/{resolve_topgg_bot_id(runtime_bot_id)}/vote"
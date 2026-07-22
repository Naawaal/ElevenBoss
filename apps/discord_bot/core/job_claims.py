# apps/discord_bot/core/job_claims.py
"""Scheduler single-owner claims (US-43 FR-016).

Reuses ``league_operation_runs`` unique ``operation_key`` insert pattern
(keys prefixed ``job:``) — no parallel claim table until ops needs it.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from apps.discord_bot.core.league_lifecycle_engine import acquire_operation, complete_operation

logger = logging.getLogger(__name__)


def job_operation_key(job_name: str, window: str) -> str:
    return f"job:{job_name}:{window}"


def utc_day_window(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.date().isoformat()


def utc_week_window(now: datetime | None = None) -> str:
    """ISO week key e.g. 2026-W30."""
    n = now or datetime.now(timezone.utc)
    iso = n.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def utc_hour_window(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H")


async def try_claim_job(
    db: Any,
    job_name: str,
    window: str,
    *,
    worker_id: str | None = None,
) -> bool:
    """Return True if this process owns the durable job for ``window``."""
    return await acquire_operation(
        db,
        job_operation_key(job_name, window),
        worker_id=worker_id,
    )


async def finish_job(
    db: Any,
    job_name: str,
    window: str,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    await complete_operation(
        db,
        job_operation_key(job_name, window),
        ok=ok,
        error=error,
    )


async def run_claimed_job(
    db: Any,
    job_name: str,
    window: str,
    work: Callable[[], Awaitable[None]],
    *,
    worker_id: str = "scheduler",
) -> bool:
    """Claim → run ``work`` → finish. Returns False if another owner holds the key."""
    if not await try_claim_job(db, job_name, window, worker_id=worker_id):
        logger.info("%s skipped — already claimed for %s", job_name, window)
        return False
    try:
        await work()
        await finish_job(db, job_name, window, ok=True)
        return True
    except Exception as exc:
        await finish_job(db, job_name, window, ok=False, error=str(exc))
        raise


__all__ = [
    "job_operation_key",
    "utc_day_window",
    "utc_week_window",
    "utc_hour_window",
    "try_claim_job",
    "finish_job",
    "run_claimed_job",
]

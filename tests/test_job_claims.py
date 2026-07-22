# tests/test_job_claims.py
"""US-43 job claim key helpers + SC-006 duplicate-claim semantics."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from apps.discord_bot.core.job_claims import (
    job_operation_key,
    run_claimed_job,
    utc_day_window,
    utc_hour_window,
    utc_week_window,
)

_SCHEDULER = (
    Path(__file__).resolve().parents[1] / "apps/discord_bot/core/scheduler_jobs.py"
).read_text(encoding="utf-8")


def test_job_operation_key_stable() -> None:
    assert job_operation_key("daily_recovery", "2026-07-22") == "job:daily_recovery:2026-07-22"


def test_window_helpers_shape() -> None:
    assert len(utc_day_window()) == 10
    assert "W" in utc_week_window()
    assert "T" in utc_hour_window()


def test_scheduler_wraps_catalog_jobs() -> None:
    for name in (
        "daily_recovery",
        "weekly_payroll",
        "season_aging",
        "youth_intake",
        "regen_pool",
        "academy_growth",
        "transfer_listing_expiry",
        "weekly_league_reset",
        "league_state_machine",
        "league_matchday_reminder",
    ):
        assert f'run_claimed_job(db, "{name}"' in _SCHEDULER


@pytest.mark.asyncio
async def test_sc006_second_claim_skips_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit stand-in for SC-006: only the first claim runs work."""
    claims = {"n": 0}

    async def fake_acquire(db, operation_key, *, worker_id=None):
        claims["n"] += 1
        return claims["n"] == 1

    finish = AsyncMock()
    monkeypatch.setattr(
        "apps.discord_bot.core.job_claims.acquire_operation",
        fake_acquire,
    )
    monkeypatch.setattr(
        "apps.discord_bot.core.job_claims.complete_operation",
        finish,
    )

    work_calls = {"n": 0}

    async def work() -> None:
        work_calls["n"] += 1

    db = object()
    assert await run_claimed_job(db, "daily_recovery", "2026-07-22", work) is True
    assert await run_claimed_job(db, "daily_recovery", "2026-07-22", work) is False
    assert work_calls["n"] == 1
    finish.assert_awaited_once()

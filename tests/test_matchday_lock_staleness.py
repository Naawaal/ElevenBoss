import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.scheduler_run import SchedulerRun, SchedulerRunStatus
from app.repositories.scheduler_run_repository import (
    mark_stale_running_jobs_failed,
    STALE_MATCHDAY_LOCK_HOURS,
)


def _utcnow():
    return datetime.now(timezone.utc)


def _make_job(status, age_hours, job_key="matchday:123:uuid:1"):
    job = MagicMock(spec=SchedulerRun)
    job.status = status
    job.job_key = job_key
    job.started_at = _utcnow() - timedelta(hours=age_hours)
    return job


@pytest.mark.asyncio
async def test_startup_sweep_recovers_stale_lock():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.rowcount = 1
    session.execute = AsyncMock(return_value=execute_result)
    cutoff = _utcnow() - timedelta(hours=STALE_MATCHDAY_LOCK_HOURS)
    count = await mark_stale_running_jobs_failed(session, job_key_prefix="matchday:", started_before=cutoff)
    assert count == 1
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_sweep_noop_on_fresh_lock():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.rowcount = 0
    session.execute = AsyncMock(return_value=execute_result)
    cutoff = _utcnow() - timedelta(hours=STALE_MATCHDAY_LOCK_HOURS)
    count = await mark_stale_running_jobs_failed(session, job_key_prefix="matchday:", started_before=cutoff)
    assert count == 0


@pytest.mark.asyncio
async def test_inline_check_recovers_stale_lock():
    from app.services.matchday_service import MatchdayService

    stale_job = _make_job(SchedulerRunStatus.RUNNING, age_hours=STALE_MATCHDAY_LOCK_HOURS + 1)
    update_result = MagicMock()
    update_result.rowcount = 1
    fresh_job = _make_job(SchedulerRunStatus.RUNNING, age_hours=0)

    with (
        patch("app.services.matchday_service.get_session") as mock_gs,
        patch("app.services.matchday_service.get_active_league_by_guild", new_callable=AsyncMock) as mock_league,
        patch("app.services.matchday_service.get_active_season_for_league", new_callable=AsyncMock) as mock_season,
        patch("app.services.matchday_service.get_job_by_key", new_callable=AsyncMock) as mock_get_job,
        patch("app.services.matchday_service.create_running_job", new_callable=AsyncMock) as mock_create_job,
        patch("app.services.matchday_service.get_current_week_fixtures_for_update", new_callable=AsyncMock, return_value=[]),
        patch("app.services.matchday_service.mark_job_failed", new_callable=AsyncMock),
    ):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=update_result)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        mock_gs.return_value = session

        league_obj = MagicMock()
        league_obj.id = "league-uuid"
        mock_league.return_value = league_obj

        season_obj = MagicMock()
        season_obj.id = "season-uuid"
        season_obj.current_week = 1
        season_obj.season_number = 1
        mock_season.return_value = season_obj

        mock_get_job.return_value = stale_job
        mock_create_job.return_value = fresh_job

        await MatchdayService.run_current_matchday(guild_id=123, discord_user_id=456, is_admin=True)
        mock_create_job.assert_awaited_once()


@pytest.mark.asyncio
async def test_inline_check_rejects_fresh_running_lock():
    from app.services.matchday_service import MatchdayService

    fresh_running = _make_job(SchedulerRunStatus.RUNNING, age_hours=0.1)
    update_result = MagicMock()
    update_result.rowcount = 0

    with (
        patch("app.services.matchday_service.get_session") as mock_gs,
        patch("app.services.matchday_service.get_active_league_by_guild", new_callable=AsyncMock) as mock_league,
        patch("app.services.matchday_service.get_active_season_for_league", new_callable=AsyncMock) as mock_season,
        patch("app.services.matchday_service.get_job_by_key", new_callable=AsyncMock) as mock_get_job,
        patch("app.services.matchday_service.create_running_job", new_callable=AsyncMock) as mock_create_job,
    ):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=update_result)
        session.flush = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        mock_gs.return_value = session

        league_obj = MagicMock()
        league_obj.id = "league-uuid"
        mock_league.return_value = league_obj

        season_obj = MagicMock()
        season_obj.id = "season-uuid"
        season_obj.current_week = 1
        season_obj.season_number = 1
        mock_season.return_value = season_obj

        mock_get_job.side_effect = [fresh_running, fresh_running]

        result = await MatchdayService.run_current_matchday(guild_id=123, discord_user_id=456, is_admin=True)
        assert result.code == "matchday_in_progress"
        mock_create_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_recovery_sweep_wins():
    from app.services.matchday_service import MatchdayService

    stale_job = _make_job(SchedulerRunStatus.RUNNING, age_hours=STALE_MATCHDAY_LOCK_HOURS + 1)
    swept_job = _make_job(SchedulerRunStatus.FAILED, age_hours=STALE_MATCHDAY_LOCK_HOURS + 1)
    update_result = MagicMock()
    update_result.rowcount = 0
    fresh_job = _make_job(SchedulerRunStatus.RUNNING, age_hours=0)

    with (
        patch("app.services.matchday_service.get_session") as mock_gs,
        patch("app.services.matchday_service.get_active_league_by_guild", new_callable=AsyncMock) as mock_league,
        patch("app.services.matchday_service.get_active_season_for_league", new_callable=AsyncMock) as mock_season,
        patch("app.services.matchday_service.get_job_by_key", new_callable=AsyncMock) as mock_get_job,
        patch("app.services.matchday_service.create_running_job", new_callable=AsyncMock) as mock_create_job,
        patch("app.services.matchday_service.get_current_week_fixtures_for_update", new_callable=AsyncMock, return_value=[]),
        patch("app.services.matchday_service.mark_job_failed", new_callable=AsyncMock),
    ):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=update_result)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        mock_gs.return_value = session

        league_obj = MagicMock()
        league_obj.id = "league-uuid"
        mock_league.return_value = league_obj

        season_obj = MagicMock()
        season_obj.id = "season-uuid"
        season_obj.current_week = 1
        season_obj.season_number = 1
        mock_season.return_value = season_obj

        mock_get_job.side_effect = [stale_job, swept_job]
        mock_create_job.return_value = fresh_job

        result = await MatchdayService.run_current_matchday(guild_id=123, discord_user_id=456, is_admin=True)
        assert result.code != "matchday_in_progress"
        mock_create_job.assert_awaited_once()

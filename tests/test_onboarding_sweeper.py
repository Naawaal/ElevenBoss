"""
Tests for the onboarding sweeper.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def make_session(status="ACTIVE", current_step="COLLECT_CLUB_NAME",
                 thread_id="11111", nudge_sent_at=None, last_activity_at=None):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.user_id = "12345"
    s.guild_id = "99999"
    s.status = status
    s.current_step = current_step
    s.thread_id = thread_id
    s.starter_message_id = None
    s.nudge_sent_at = nudge_sent_at
    s.completing_at = None
    now = datetime.now(timezone.utc)
    s.last_activity_at = last_activity_at or (now - timedelta(minutes=5))
    s.collected_data = {"club_name": "TestClub"}
    s.cleanup_after = None
    return s


@pytest.mark.asyncio
async def test_nudge_inactive_sends_nudge():
    """Sessions that are idle ≥10 min should receive a nudge."""
    from app.onboarding.sweeper import _nudge_inactive_sessions
    fake_session = make_session()
    bot = MagicMock()

    with (
        patch("app.onboarding.sweeper.get_session") as mock_gs,
        patch("app.onboarding.sweeper.onb_repo.get_nudgeable_sessions", new_callable=AsyncMock, return_value=[fake_session]),
        patch("app.onboarding.sweeper.renderers.send_nudge", new_callable=AsyncMock) as mock_nudge,
        patch("app.onboarding.sweeper.onb_repo.mark_nudge_sent", new_callable=AsyncMock) as mock_mark,
    ):
        db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await _nudge_inactive_sessions(bot)

    mock_nudge.assert_awaited_once()
    # mark_nudge_sent requires its own session; called in a separate context
    mock_mark.assert_awaited_once()


@pytest.mark.asyncio
async def test_abandon_expired_sessions_marks_abandoned():
    """Sessions idle ≥15 min should be marked ABANDONED."""
    from app.onboarding.sweeper import _abandon_expired_sessions
    fake_session = make_session()
    bot = MagicMock()

    with (
        patch("app.onboarding.sweeper.get_session") as mock_gs,
        patch("app.onboarding.sweeper.onb_repo.get_abandonment_due_sessions", new_callable=AsyncMock, return_value=[fake_session]),
        patch("app.onboarding.sweeper.onb_repo.mark_abandoned", new_callable=AsyncMock) as mock_abandon,
    ):
        db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await _abandon_expired_sessions(bot)

    mock_abandon.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_due_threads_archives_thread():
    """Sessions past cleanup_after should have their threads archived."""
    from app.onboarding.sweeper import _cleanup_due_threads
    fake_session = make_session(status="COMPLETED")
    fake_session.cleanup_after = datetime.now(timezone.utc) - timedelta(seconds=1)
    bot = MagicMock()

    with (
        patch("app.onboarding.sweeper.get_session") as mock_gs,
        patch("app.onboarding.sweeper.onb_repo.get_cleanup_due_sessions", new_callable=AsyncMock, return_value=[fake_session]),
        patch("app.onboarding.sweeper.renderers.archive_thread", new_callable=AsyncMock) as mock_archive,
        patch("app.onboarding.sweeper.onb_repo.update_cleanup_state", new_callable=AsyncMock),
    ):
        db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await _cleanup_due_threads(bot)

    mock_archive.assert_awaited_once()


@pytest.mark.asyncio
async def test_recover_stuck_completing_sessions_retriggers_completion():
    """COMPLETING sessions stuck >5 min should re-trigger complete_registration."""
    from app.onboarding.sweeper import _recover_stuck_completing_sessions
    stuck = make_session(status="COMPLETING")
    stuck.completing_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    bot = MagicMock()

    with (
        patch("app.onboarding.sweeper.get_session") as mock_gs,
        patch("app.onboarding.sweeper.onb_repo.get_stuck_completing_sessions", new_callable=AsyncMock, return_value=[stuck]),
        patch("app.services.onboarding_service.OnboardingService.complete_registration", new_callable=AsyncMock) as mock_complete,
    ):
        from app.onboarding import sweeper

        db = AsyncMock()
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        await _recover_stuck_completing_sessions(bot)



    mock_complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_sweeper_graceful_on_nudge_failure():
    """If nudge sending fails, sweep continues and does not raise."""
    from app.onboarding.sweeper import sweep_onboarding_sessions
    bot = MagicMock()

    with (
        patch("app.onboarding.sweeper._nudge_inactive_sessions", new_callable=AsyncMock, side_effect=RuntimeError("nudge failed")),
        patch("app.onboarding.sweeper._abandon_expired_sessions", new_callable=AsyncMock),
        patch("app.onboarding.sweeper._cleanup_due_threads", new_callable=AsyncMock),
        patch("app.onboarding.sweeper._recover_stuck_completing_sessions", new_callable=AsyncMock),
    ):
        # Should not raise even when sub-task raises
        await sweep_onboarding_sessions(bot)

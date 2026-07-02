"""
Onboarding sweeper — cleans up stale/completed onboarding sessions.
Runs on an APScheduler interval (every 2 minutes).
"""
import logging
from datetime import datetime, timezone
import discord
from app.db.session import get_session
from app.repositories import onboarding_repository as onb_repo
from app.onboarding import renderers
from app.error_reporting import capture_exception

logger = logging.getLogger("app.onboarding.sweeper")


async def sweep_onboarding_sessions(bot: discord.Client) -> None:
    """Main sweeper entry — runs all sub-tasks in order."""
    try:
        await _nudge_inactive_sessions(bot)
    except Exception as e:
        logger.error(f"sweeper.nudge failed: {e}", exc_info=e)
        capture_exception(e)
    try:
        await _abandon_expired_sessions(bot)
    except Exception as e:
        logger.error(f"sweeper.abandon failed: {e}", exc_info=e)
        capture_exception(e)
    try:
        await _cleanup_due_threads(bot)
    except Exception as e:
        logger.error(f"sweeper.cleanup failed: {e}", exc_info=e)
        capture_exception(e)
    try:
        await _recover_stuck_completing_sessions(bot)
    except Exception as e:
        logger.error(f"sweeper.recover failed: {e}", exc_info=e)
        capture_exception(e)


async def _nudge_inactive_sessions(bot: discord.Client) -> None:
    """
    Send an inactivity nudge to sessions that have been idle for ≥10 min
    but have not yet been nudged.
    """
    async with get_session() as session:
        sessions = await onb_repo.get_nudgeable_sessions(session)

    for onb in sessions:
        try:
            await renderers.send_nudge(bot, onb)
            async with get_session() as session:
                await onb_repo.mark_nudge_sent(session, onb.id)
            logger.info(f"sweeper.nudge_sent: session={onb.id}")
        except Exception as e:
            logger.warning(f"sweeper.nudge failed for session {onb.id}: {e}")


async def _abandon_expired_sessions(bot: discord.Client) -> None:
    """
    Mark ACTIVE sessions that have been idle for ≥15 min as ABANDONED.
    The cleanup_after is set to now() so the thread cleanup runs immediately.
    """
    async with get_session() as session:
        sessions = await onb_repo.get_abandonment_due_sessions(session)

    for onb in sessions:
        try:
            async with get_session() as session:
                await onb_repo.mark_abandoned(session, onb.id)
            logger.info(f"sweeper.abandoned: session={onb.id}, user={onb.user_id}")
        except Exception as e:
            logger.warning(f"sweeper.abandon failed for session {onb.id}: {e}")


async def _cleanup_due_threads(bot: discord.Client) -> None:
    """
    Archive threads for sessions whose cleanup_after has passed.
    Handles COMPLETED, ABANDONED, and FAILED sessions.
    """
    async with get_session() as session:
        sessions = await onb_repo.get_cleanup_due_sessions(session)

    for onb in sessions:
        attempted_at = datetime.now(timezone.utc)
        error: str | None = None
        try:
            if onb.thread_id:
                await renderers.archive_thread(
                    bot,
                    onb.thread_id,
                    delete_starter_message_id=onb.starter_message_id,
                )
            logger.info(f"sweeper.thread_archived: session={onb.id}")
        except Exception as e:
            error = str(e)
            logger.warning(f"sweeper.cleanup failed for session {onb.id}: {e}")

        try:
            async with get_session() as session:
                await onb_repo.update_cleanup_state(session, onb.id, attempted_at, error)
        except Exception as e:
            logger.error(f"sweeper.cleanup_state_update failed for session {onb.id}: {e}")


async def _recover_stuck_completing_sessions(bot: discord.Client) -> None:
    """
    COMPLETING sessions stuck for >5 min may have been interrupted mid-completion.
    Re-trigger completion for each.
    """
    async with get_session() as session:
        sessions = await onb_repo.get_stuck_completing_sessions(session)

    for onb in sessions:
        logger.warning(
            f"sweeper.recover_stuck: session={onb.id}, user={onb.user_id}, "
            f"completing_at={onb.completing_at}"
        )
        try:
            from app.services.onboarding_service import OnboardingService
            await OnboardingService.complete_registration(
                bot=bot,
                session_id=onb.id,
                guild_id=onb.guild_id,
            )
        except Exception as e:
            logger.error(f"sweeper.recover failed for session {onb.id}: {e}", exc_info=e)
            capture_exception(e)

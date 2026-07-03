"""
Friendly sweeper — cleans up completed and orphaned friendly match threads.
Runs on an APScheduler interval (every 2 minutes).
"""
import logging
from datetime import datetime, timezone
import discord

from app.db.session import get_session
from app.repositories import friendly_repository as friendly_repo
from app.error_reporting import capture_exception

logger = logging.getLogger("app.scheduler.friendly_sweeper")

async def sweep_friendly_threads(bot: discord.Client) -> None:
    """
    Main entry point for sweeping completed and orphaned friendly match threads.
    """
    try:
        await _cleanup_completed_threads(bot)
    except Exception as e:
        logger.error(f"friendly_sweeper.completed failed: {e}", exc_info=e)
        capture_exception(e)

    try:
        await _cleanup_orphaned_threads(bot)
    except Exception as e:
        logger.error(f"friendly_sweeper.orphaned failed: {e}", exc_info=e)
        capture_exception(e)

async def _cleanup_completed_threads(bot: discord.Client) -> None:
    """
    Delete completed match threads that are due for cleanup.
    """
    async with get_session() as session:
        breadcrumbs = await friendly_repo.get_cleanup_due_breadcrumbs(session)

    for crumb in breadcrumbs:
        attempted_at = datetime.now(timezone.utc)
        error: str | None = None
        
        try:
            await _delete_thread_and_parent(bot, crumb.thread_id, crumb.parent_message_id)
            logger.info(f"friendly_sweeper: deleted completed thread {crumb.thread_id}")
            
            # Delete breadcrumb from DB on success
            async with get_session() as session:
                await friendly_repo.delete_breadcrumb(session, crumb.id)
                await session.commit()
        except discord.NotFound:
            # Already deleted
            logger.info(f"friendly_sweeper: thread {crumb.thread_id} already deleted (NotFound)")
            async with get_session() as session:
                await friendly_repo.delete_breadcrumb(session, crumb.id)
                await session.commit()
        except discord.Forbidden:
            # Missing permissions (permanent error, remove row)
            logger.warning(f"friendly_sweeper: missing permission to delete thread {crumb.thread_id} (Forbidden)")
            async with get_session() as session:
                await friendly_repo.delete_breadcrumb(session, crumb.id)
                await session.commit()
        except Exception as e:
            # Other errors (e.g. transient API/network issue), keep row and log error
            error = str(e)
            logger.warning(f"friendly_sweeper: failed to clean up thread {crumb.thread_id}: {e}")
            async with get_session() as session:
                await friendly_repo.update_breadcrumb_cleanup_error(session, crumb.id, attempted_at, error)
                await session.commit()

async def _cleanup_orphaned_threads(bot: discord.Client) -> None:
    """
    Recover and delete orphaned threads where status remains PLAYING after max match duration (10 mins).
    """
    async with get_session() as session:
        breadcrumbs = await friendly_repo.get_dangling_breadcrumbs(session, max_duration_minutes=10)

    for crumb in breadcrumbs:
        attempted_at = datetime.now(timezone.utc)
        error: str | None = None
        
        try:
            await _delete_thread_and_parent(bot, crumb.thread_id, crumb.parent_message_id)
            logger.info(f"friendly_sweeper: cleaned up orphaned thread {crumb.thread_id}")
            
            # Delete breadcrumb from DB on success
            async with get_session() as session:
                await friendly_repo.delete_breadcrumb(session, crumb.id)
                await session.commit()
        except discord.NotFound:
            logger.info(f"friendly_sweeper: orphaned thread {crumb.thread_id} already deleted (NotFound)")
            async with get_session() as session:
                await friendly_repo.delete_breadcrumb(session, crumb.id)
                await session.commit()
        except discord.Forbidden:
            logger.warning(f"friendly_sweeper: missing permission to delete orphaned thread {crumb.thread_id} (Forbidden)")
            async with get_session() as session:
                await friendly_repo.delete_breadcrumb(session, crumb.id)
                await session.commit()
        except Exception as e:
            error = str(e)
            logger.warning(f"friendly_sweeper: failed to clean up orphaned thread {crumb.thread_id}: {e}")
            async with get_session() as session:
                await friendly_repo.update_breadcrumb_cleanup_error(session, crumb.id, attempted_at, error)
                await session.commit()

async def _delete_thread_and_parent(
    bot: discord.Client,
    thread_id: str,
    parent_message_id: str | None
) -> None:
    """
    Helper to delete the thread and its parent starter message, if exists.
    """
    # Fetch thread (exceptions like NotFound/Forbidden will bubble up naturally with correct response objects)
    channel = await bot.fetch_channel(int(thread_id))
        
    if not isinstance(channel, discord.Thread):
        raise ValueError("Channel is not a thread")

    # Delete parent starter message if provided
    if parent_message_id:
        parent = channel.parent
        if not parent and hasattr(channel, "parent_id") and channel.parent_id:
            try:
                parent = await bot.fetch_channel(channel.parent_id)
            except Exception:
                parent = None
        if parent:
            try:
                starter_msg = await parent.fetch_message(int(parent_message_id))
                await starter_msg.delete()
                logger.info(f"friendly_sweeper: deleted parent message {parent_message_id}")
            except Exception as pe:
                logger.warning(f"friendly_sweeper: could not delete parent message {parent_message_id}: {pe}")

    # Delete thread channel
    await channel.delete()

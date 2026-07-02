# app/scheduler/scheduler.py

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scheduler.game_loop_jobs import run_game_loop_tick
from app.onboarding.sweeper import sweep_onboarding_sessions

logger = logging.getLogger("app.scheduler.scheduler")
_scheduler: AsyncIOScheduler | None = None

def start_scheduler(bot) -> None:
    """
    Initialize and start the recurring background orchestrator tick.
    """
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler is already running.")
        return
        
    try:
        _scheduler = AsyncIOScheduler()
        # Add the check tick job every 1 minute
        _scheduler.add_job(
            run_game_loop_tick,
            "interval",
            minutes=1,
            args=[bot],
            id="game_loop_tick",
            replace_existing=True
        )
        # Onboarding sweeper: nudge idle sessions, archive completed threads
        _scheduler.add_job(
            sweep_onboarding_sessions,
            "interval",
            minutes=2,
            args=[bot],
            id="onboarding_sweeper",
            replace_existing=True
        )
        _scheduler.start()
        logger.info("scheduler_started")
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e

def shutdown_scheduler() -> None:
    """
    Stop the background scheduler gracefully.
    """
    global _scheduler
    if _scheduler is None:
        logger.warning("Scheduler is not running.")
        return
        
    try:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler_stopped")
    except Exception as e:
        logger.error(f"Failed to stop background scheduler: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)

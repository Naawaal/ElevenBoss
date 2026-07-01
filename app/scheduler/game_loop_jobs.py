# app/scheduler/game_loop_jobs.py

import logging
from datetime import datetime
from app.services.game_loop_orchestrator import GameLoopOrchestrator
from app.services.announcement_service import AnnouncementService

logger = logging.getLogger("app.scheduler.game_loop_jobs")

async def run_game_loop_tick(bot) -> None:
    """
    Background job function invoked by the scheduler every tick.
    """
    logger.info("orchestrator_tick_started")
    try:
        # Bind the bot client to the AnnouncementService
        AnnouncementService.bot = bot
        
        # Instantiate and run due orchestrator checks
        orchestrator = GameLoopOrchestrator(bot)
        result = await orchestrator.run_due_checks()
        logger.info(f"orchestrator_tick_finished: success={result.success}, code={result.code}")
    except Exception as e:
        logger.error(f"automation_error: game loop tick crashed: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)

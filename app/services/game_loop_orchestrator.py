# app/services/game_loop_orchestrator.py

import logging
import traceback
from datetime import datetime
from dataclasses import dataclass, field
import uuid

from app.db.session import get_session
from app.repositories.guild_config_repository import get_or_create_guild_config
from app.repositories.league_repository import get_active_league_by_guild
from app.repositories.season_repository import get_active_season_for_league
from app.repositories.scheduler_run_repository import get_job_by_key
from app.services.league_lifecycle_service import LeagueLifecycleService
from app.services.matchday_service import MatchdayService
from app.services.announcement_service import AnnouncementService
from app.services.schedule_service import ScheduleService
from app.models.season import SeasonStatus
from app.models.league import LeagueStatus
from app.models.scheduler_run import SchedulerRunStatus

logger = logging.getLogger("app.services.game_loop_orchestrator")

@dataclass
class AutomationStepResult:
    success: bool
    code: str
    message: str
    action: str | None = None
    guild_id: int | None = None
    league_id: str | None = None
    season_id: str | None = None
    week: int | None = None

@dataclass
class GuildAutomationResult:
    success: bool
    guild_id: int
    lifecycle_result: AutomationStepResult | None = None
    matchday_result: AutomationStepResult | None = None

@dataclass
class GameLoopRunResult:
    success: bool
    code: str
    message: str
    guild_results: list[GuildAutomationResult] = field(default_factory=list)

class GameLoopOrchestrator:
    def __init__(self, bot=None):
        self.bot = bot

    async def run_due_checks(self, now_utc: datetime | None = None) -> GameLoopRunResult:
        """
        Scan all active guilds connected to the bot and run lifecycle and matchday due checks.
        Shields other guilds from any failure in one specific guild.
        """
        if now_utc is None:
            now_utc = datetime.utcnow()

        logger.info("orchestrator_tick_started")
        guild_results = []
        
        # Get list of guild IDs from bot guilds
        guild_ids = []
        if self.bot and hasattr(self.bot, "guilds"):
            guild_ids = [g.id for g in self.bot.guilds]
            
        logger.info(f"orchestrator_tick_scanning: guild_count={len(guild_ids)}")

        for g_id in guild_ids:
            try:
                res = await self.run_guild_check(g_id, now_utc)
                guild_results.append(res)
            except Exception as e:
                logger.error(f"automation_error: failed to run guild check for guild_id={g_id}: {e}", exc_info=e)
                from app.error_reporting import capture_exception
                capture_exception(e)
                guild_results.append(GuildAutomationResult(success=False, guild_id=g_id))

        logger.info("orchestrator_tick_finished")
        return GameLoopRunResult(
            success=True,
            code="success",
            message="Automation checks completed.",
            guild_results=guild_results
        )

    async def run_guild_check(self, guild_id: int, now_utc: datetime | None = None) -> GuildAutomationResult:
        """
        Run both league lifecycle and matchday due automation checks for a specific guild.
        Updates last automation run status and metrics.
        """
        if now_utc is None:
            now_utc = datetime.utcnow()

        logger.info(f"orchestrator_guild_check_started: guild_id={guild_id}")
        
        # 1. Run league lifecycle check
        lifecycle_res = await self.run_league_lifecycle_check(guild_id)
        
        # 2. Run matchday check
        matchday_res = await self.run_matchday_due_check(guild_id, now_utc)
        
        # 3. Update automation metrics in GuildConfig
        last_status = "idle"
        last_error = None
        
        if (lifecycle_res and not lifecycle_res.success) or (matchday_res and not matchday_res.success):
            success = False
            # Get code of the first failure
            err_res = lifecycle_res if (lifecycle_res and not lifecycle_res.success) else matchday_res
            last_status = err_res.code
            last_error = err_res.message
        else:
            success = True
            # Determine success code
            if matchday_res and matchday_res.action == "matchday_simulated":
                last_status = matchday_res.code  # Can be success or simulation_success_announcement_failed
            elif lifecycle_res and lifecycle_res.action == "league_started":
                last_status = lifecycle_res.code
            else:
                last_status = "success"

        try:
            async with get_session() as session:
                config = await get_or_create_guild_config(session, guild_id)
                config.last_automation_run_at = now_utc
                config.last_automation_status = last_status
                config.last_automation_error = last_error
                config.automation_status = "idle"
        except Exception as e:
            logger.error(f"Failed to save automation metrics for guild_id={guild_id}: {e}", exc_info=e)

        logger.info(f"orchestrator_guild_check_finished: guild_id={guild_id}, success={success}, status={last_status}")
        return GuildAutomationResult(
            success=success,
            guild_id=guild_id,
            lifecycle_result=lifecycle_res,
            matchday_result=matchday_res
        )

    async def run_league_lifecycle_check(self, guild_id: int) -> AutomationStepResult:
        """
        Check if any league lifecycle changes are due (auto-start).
        """
        logger.info(f"auto_league_start_check: guild_id={guild_id}")
        
        # Mark config as processing lifecycle
        try:
            async with get_session() as session:
                config = await get_or_create_guild_config(session, guild_id)
                config.automation_status = "running_lifecycle"
        except Exception as e:
            logger.warning(f"Could not update status to running_lifecycle: {e}")

        # Check and trigger auto start
        result = await LeagueLifecycleService.check_and_trigger_auto_start(guild_id)
        if not result:
            return AutomationStepResult(success=True, code="skipped_not_due", message="League start conditions not met.")

        if result.success:
            logger.info(f"auto_league_start_triggered: league started in guild_id={guild_id}")
            # Try announcement
            announced = await AnnouncementService.announce_league_start(guild_id, result.league_name)
            if not announced:
                return AutomationStepResult(
                    success=True,
                    code="league_started_announcement_failed",
                    message="League started automatically, but Discord announcement failed.",
                    action="league_started",
                    guild_id=guild_id,
                    league_id=str(result.league_id),
                    season_id=str(result.season_id)
                )
            return AutomationStepResult(
                success=True,
                code="success",
                message="League started automatically and announced successfully.",
                action="league_started",
                guild_id=guild_id,
                league_id=str(result.league_id),
                season_id=str(result.season_id)
            )
        else:
            logger.error(f"auto_league_start_failed: start league failed in guild_id={guild_id}: {result.message}")
            return AutomationStepResult(
                success=False,
                code=result.code,
                message=result.message,
                action="league_started"
            )

    async def run_matchday_due_check(self, guild_id: int, now_utc: datetime) -> AutomationStepResult:
        """
        Check if scheduled matchday is due, and simulate it.
        """
        logger.info(f"scheduled_matchday_check: guild_id={guild_id}")
        
        # 1. Fetch guild config and verify matchday is enabled
        try:
            async with get_session() as session:
                config = await get_or_create_guild_config(session, guild_id)
                if not config.matchday_enabled:
                    return AutomationStepResult(success=True, code="skipped_disabled", message="Matchday schedule is disabled.")
                
                # Check if due
                due = ScheduleService.is_matchday_due(config, now_utc)
                if not due:
                    return AutomationStepResult(success=True, code="skipped_not_due", message="Scheduled time has not arrived.")

                # Retrieve active league & season
                league = await get_active_league_by_guild(session, guild_id)
                if not league or league.status != LeagueStatus.ACTIVE:
                    return AutomationStepResult(success=True, code="skipped_no_active_league", message="No active league found.")
                
                season = await get_active_season_for_league(session, guild_id, league.id)
                if not season or season.status != SeasonStatus.ACTIVE:
                    return AutomationStepResult(success=True, code="skipped_no_active_season", message="No active season found.")
                
                current_week = season.current_week
                season_id = season.id
                league_id = league.id
                
        except Exception as e:
            logger.error(f"Failed to fetch config for matchday due check in guild_id={guild_id}: {e}", exc_info=e)
            return AutomationStepResult(success=False, code="database_error", message=f"Database error checking schedule: {e}")

        # Idempotency check before triggering simulation
        job_key = f"matchday:{guild_id}:{season_id}:{current_week}"
        try:
            async with get_session() as session:
                job = await get_job_by_key(session, job_key)
                if job and job.status == SchedulerRunStatus.SUCCESS:
                    logger.info(f"scheduled_matchday_skipped: reason=already_played, job_key={job_key}")
                    return AutomationStepResult(
                        success=True,
                        code="skipped_already_processed",
                        message=f"Matchday for Week {current_week} already simulated.",
                        guild_id=guild_id,
                        league_id=str(league_id),
                        season_id=str(season_id),
                        week=current_week
                    )
                elif job and job.status == SchedulerRunStatus.RUNNING:
                    logger.info(f"scheduled_matchday_skipped: reason=job_in_progress, job_key={job_key}")
                    return AutomationStepResult(
                        success=True,
                        code="skipped_already_processed",
                        message=f"Matchday simulation is already in progress.",
                        guild_id=guild_id,
                        league_id=str(league_id),
                        season_id=str(season_id),
                        week=current_week
                    )
        except Exception as e:
            logger.error(f"Failed during idempotency check: {e}")
            return AutomationStepResult(success=False, code="database_error", message=f"Idempotency check error: {e}")

        # 2. Mark config as simulating
        try:
            async with get_session() as session:
                config = await get_or_create_guild_config(session, guild_id)
                config.automation_status = "simulating_matchday"
        except Exception as e:
            logger.warning(f"Could not update status to simulating_matchday: {e}")

        # 3. Simulate Matchday
        bot_user_id = self.bot.user.id if (self.bot and self.bot.user) else 0
        logger.info(f"scheduled_matchday_due: simulating week={current_week} in guild_id={guild_id}")
        
        sim_res = await MatchdayService.run_current_matchday(
            guild_id=guild_id,
            discord_user_id=bot_user_id,
            is_admin=True
        )
        
        if not sim_res.success:
            logger.error(f"scheduled_matchday_failed: simulation failed: {sim_res.message}")
            return AutomationStepResult(
                success=False,
                code=sim_res.code,
                message=sim_res.message,
                action="matchday_simulated",
                guild_id=guild_id,
                league_id=str(league_id),
                season_id=str(season_id),
                week=current_week
            )

        # Matchday succeeded, now post announcement
        logger.info(f"scheduled_matchday_success: week={current_week} simulated, sending announcements...")
        announced = await AnnouncementService.announce_matchday_summary(guild_id, current_week, sim_res.results)
        
        # Check if season completed
        if sim_res.season_completed:
            # Announce season completion
            await AnnouncementService.announce_season_complete(guild_id, sim_res.season_number)

        if not announced:
            logger.warning(f"scheduled_matchday_success: Discord announcement failed for guild_id={guild_id}")
            return AutomationStepResult(
                success=True,
                code="simulation_success_announcement_failed",
                message="Matches simulated successfully, but Discord announcement failed.",
                action="matchday_simulated",
                guild_id=guild_id,
                league_id=str(league_id),
                season_id=str(season_id),
                week=current_week
            )
            
        return AutomationStepResult(
            success=True,
            code="success",
            message="Matchday simulated and announced successfully.",
            action="matchday_simulated",
            guild_id=guild_id,
            league_id=str(league_id),
            season_id=str(season_id),
            week=current_week
        )

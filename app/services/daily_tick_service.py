# app/services/daily_tick_service.py

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.club import Club
from app.models.player import Player
from app.models.daily_tick_runs import DailyTickRun, DailyTickRunStatus
from app.models.facility import Facility, FacilityType, FacilityStatus
from app.config import config
from app.repositories.guild_config_repository import get_or_create_guild_config

logger = logging.getLogger("app.services.daily_tick_service")

class DailyTickService:
    @staticmethod
    async def run_daily_tick(
        session: AsyncSession,
        guild_id: int,
        now_utc: datetime | None = None
    ) -> DailyTickRun | None:
        """
        Executes the daily state update (tick) for a guild:
        - Processes completed facility upgrades.
        - Recovers fitness for healthy players, with training pitch bonuses.
        - Recovers fitness for injured players (at a lower rate), with medical clinic bonuses.
        - Decrements remaining injury days for injured players (excluding same-day injuries).
        - Restores baseline fitness upon recovery.
        
        Fully idempotent: runs exactly once per calendar day per guild.
        """
        if now_utc is None:
            now_utc = datetime.utcnow()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # Retrieve guild config to determine the timezone
        guild_config = await get_or_create_guild_config(session, guild_id)
        guild_tz = ZoneInfo(guild_config.matchday_timezone)
        local_now = now_utc.astimezone(guild_tz)
        current_date = local_now.date()

        # Check for existing run today
        stmt = select(DailyTickRun).where(
            and_(
                DailyTickRun.guild_id == str(guild_id),
                DailyTickRun.tick_date == current_date
            )
        )
        res = await session.execute(stmt)
        existing_run = res.scalar_one_or_none()

        run_to_use = None
        if existing_run:
            if existing_run.status == DailyTickRunStatus.SUCCESS:
                logger.info(f"daily_tick_skipped: already_succeeded, guild_id={guild_id}, date={current_date}")
                return None
            
            elif existing_run.status == DailyTickRunStatus.RUNNING:
                started_at_aware = existing_run.started_at
                if started_at_aware.tzinfo is None:
                    started_at_aware = started_at_aware.replace(tzinfo=timezone.utc)
                
                age_seconds = (now_utc - started_at_aware).total_seconds()
                if age_seconds < 1800:
                    logger.info(f"daily_tick_skipped: run_in_progress, guild_id={guild_id}, date={current_date}, age={age_seconds}s")
                    return None
                else:
                    logger.warning(f"daily_tick_stale_lock_recovered: guild_id={guild_id}, date={current_date}, age={age_seconds}s")
                    # Recover stale lock by marking as failed and retrying
                    existing_run.status = DailyTickRunStatus.FAILED
                    existing_run.finished_at = now_utc
                    existing_run.error = "Stale run recovered and retried"
                    await session.flush()
                    
                    # Reset for retry
                    existing_run.status = DailyTickRunStatus.RUNNING
                    existing_run.started_at = now_utc
                    existing_run.finished_at = None
                    existing_run.error = None
                    run_to_use = existing_run
            
            elif existing_run.status == DailyTickRunStatus.FAILED:
                logger.info(f"daily_tick_retry_failed_run: guild_id={guild_id}, date={current_date}")
                # Reset for retry
                existing_run.status = DailyTickRunStatus.RUNNING
                existing_run.started_at = now_utc
                existing_run.finished_at = None
                existing_run.error = None
                run_to_use = existing_run
        else:
            # Create a new run
            run_to_use = DailyTickRun(
                guild_id=str(guild_id),
                tick_date=current_date,
                status=DailyTickRunStatus.RUNNING,
                started_at=now_utc
            )
            session.add(run_to_use)
            
        await session.flush()

        try:
            # 1. Process completed facility upgrades for clubs in this guild
            # selectinload(Facility.club) is required to eagerly load the club relationship
            # in a single async round-trip. Accessing fac.club lazily in an async session
            # triggers MissingGreenlet because asyncpg cannot perform synchronous IO.
            upgrade_stmt = (
                select(Facility)
                .join(Club)
                .where(
                    and_(
                        Club.guild_id == str(guild_id),
                        Facility.status == FacilityStatus.UPGRADING,
                        Facility.upgrade_completes_at <= now_utc
                    )
                )
                .options(selectinload(Facility.club))
            )
            upgrades_res = await session.execute(upgrade_stmt)
            completed_upgrades = upgrades_res.scalars().all()

            for fac in completed_upgrades:
                fac.level += 1
                if fac.level >= config.FACILITY_MAX_LEVEL:
                    fac.status = FacilityStatus.MAX_LEVEL
                else:
                    fac.status = FacilityStatus.IDLE
                
                fac.upgrade_started_at = None
                fac.upgrade_completes_at = None
                
                # If stadium capacity upgrade completes, update club stadium capacity
                if fac.facility_type == FacilityType.STADIUM:
                    fac.club.stadium_capacity = config.STADIUM_CAPACITY_BY_LEVEL.get(fac.level, fac.club.stadium_capacity)
                    logger.info(f"Stadium capacity upgrade completed. Club: {fac.club.name}, New capacity: {fac.club.stadium_capacity}")
                else:
                    logger.info(f"Facility upgrade completed. Club: {fac.club.name}, Facility: {fac.facility_type.value}, New level: {fac.level}")

            # 2. Fetch all facilities for clubs in this guild to determine levels/bonuses
            fac_stmt = select(Facility).join(Club).where(Club.guild_id == str(guild_id))
            fac_res = await session.execute(fac_stmt)
            facilities_by_club = {}
            for fac in fac_res.scalars().all():
                if fac.club_id not in facilities_by_club:
                    facilities_by_club[fac.club_id] = {}
                facilities_by_club[fac.club_id][fac.facility_type] = fac.level

            # 3. Calculate the cutoff for same-day injury protection (start of today in UTC)
            start_of_today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)

            # 4. Fetch all active (non-retired) players for this guild
            players_stmt = select(Player).where(
                and_(
                    Player.guild_id == str(guild_id),
                    Player.is_retired == False
                )
            )
            players_res = await session.execute(players_stmt)
            players = players_res.scalars().all()

            for p in players:
                # Resolve facility bonuses
                club_facs = facilities_by_club.get(p.club_id, {})
                training_pitch_level = club_facs.get(FacilityType.TRAINING_PITCH, 1)
                medical_clinic_level = club_facs.get(FacilityType.MEDICAL_CLINIC, 1)

                training_pitch_bonus = config.TRAINING_PITCH_RECOVERY_BONUS.get(training_pitch_level, 0)
                medical_clinic_bonus = config.MEDICAL_CLINIC_INJURY_RECOVERY_BONUS.get(medical_clinic_level, 0)

                is_injured = p.injury_days_remaining > 0
                if is_injured:
                    # Injured players recover fitness slower, but aided by medical clinic level
                    p.fitness = min(100, p.fitness + config.DAILY_INJURED_FITNESS_RECOVERY + medical_clinic_bonus)
                    
                    # Check same-day injury protection
                    created_at_aware = p.injury_created_at
                    if created_at_aware is not None:
                        if created_at_aware.tzinfo is None:
                            created_at_aware = created_at_aware.replace(tzinfo=timezone.utc)
                        
                        if created_at_aware < start_of_today_utc:
                            p.injury_days_remaining = max(0, p.injury_days_remaining - 1)
                            
                            # If they recovered today, clean the injury fields and restore baseline fitness to max(fitness, 80)
                            if p.injury_days_remaining == 0:
                                p.injury_type = None
                                p.injury_severity = None
                                p.injury_created_at = None
                                p.fitness = max(p.fitness, 80)
                                logger.info(f"Player {p.display_name} recovered from injury. Fitness set to {p.fitness}")
                else:
                    # Healthy players recover fitness faster, boosted by training pitch level
                    p.fitness = min(100, p.fitness + config.DAILY_FITNESS_RECOVERY + training_pitch_bonus)

            run_to_use.status = DailyTickRunStatus.SUCCESS
            run_to_use.finished_at = now_utc
            await session.flush()
            
            logger.info(f"daily_tick_success: guild_id={guild_id}, date={current_date}")
            return run_to_use

        except Exception as e:
            # Mark the run as failed
            run_to_use.status = DailyTickRunStatus.FAILED
            run_to_use.finished_at = now_utc
            import traceback
            run_to_use.error = traceback.format_exc()
            await session.flush()
            logger.error(f"daily_tick_failed: guild_id={guild_id}, date={current_date}, error={e}", exc_info=e)
            raise e

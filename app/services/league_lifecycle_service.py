# app/services/league_lifecycle_service.py

import logging
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_session
from app.repositories.league_repository import get_draft_league_by_guild, get_joined_player_user_ids
from app.repositories.club_repository import get_clubs_in_league
from app.services.league_service import start_league, LeagueResult
from app.services.announcement_service import AnnouncementService
from app.models.league import League, LeagueStatus
from app.models.club import Club
from app.models.manager import Manager

logger = logging.getLogger("app.services.league_lifecycle_service")

class LeagueLifecycleService:
    @staticmethod
    async def check_and_trigger_auto_start(guild_id: int | str) -> LeagueResult | None:
        """
        Check if the draft league in a guild satisfies auto-start conditions.
        If yes, trigger start_league and return the result. Otherwise return None.
        """
        try:
            async with get_session() as session:
                league = await get_draft_league_by_guild(session, guild_id)
                if not league or league.status != LeagueStatus.DRAFT:
                    logger.debug(f"lifecycle_check_skipped: no draft league in guild_id={guild_id}")
                    return None

                # If no deadline is set, do nothing
                if not league.registration_deadline_at:
                    logger.debug(f"lifecycle_check_skipped: no registration deadline set for guild_id={guild_id}")
                    return None

                now_utc = datetime.now(timezone.utc)
                
                # Case 1: Deadline has not passed
                if now_utc < league.registration_deadline_at:
                    logger.debug(f"lifecycle_check_skipped: registration deadline not reached for guild_id={guild_id}")
                    return None

                # Deadline has passed! Count human clubs and total clubs
                clubs = await get_clubs_in_league(session, guild_id, league.id)
                human_clubs = [c for c in clubs if not c.is_bot_controlled]
                human_count = len(human_clubs)
                total_count = len(clubs)
                
                # Fetch joined manager user IDs for player notifications
                joined_player_user_ids = await get_joined_player_user_ids(session, league.id)

                league_id = league.id
                league_name = league.name
                auto_start_after_deadline = league.auto_start_after_deadline
                fill_bots_after_deadline = league.fill_bots_after_deadline
                minimum_human_clubs = league.minimum_human_clubs
                target_club_count = league.target_club_count

            # Process Cases
            
            # Case 2: Deadline passed but auto-start is disabled
            if not auto_start_after_deadline:
                reason = "Auto-start is disabled for this league."
                await LeagueLifecycleService.transition_to_review(league_id, reason, guild_id, joined_player_user_ids)
                return LeagueResult(success=False, code="needs_admin_review", message=reason, league_id=league_id, league_name=league_name)

            # Case 3: Deadline passed and not enough humans joined
            if human_count < minimum_human_clubs:
                reason = f"Minimum humans required ({minimum_human_clubs}) not met. Only {human_count} joined."
                await LeagueLifecycleService.transition_to_review(league_id, reason, guild_id, joined_player_user_ids)
                return LeagueResult(success=False, code="needs_admin_review", message=reason, league_id=league_id, league_name=league_name)

            # Case 4: Deadline passed, league is full with humans
            if total_count == target_club_count:
                logger.info(f"lifecycle_check_start: Case 4 (full human) triggered for guild_id={guild_id}")
                result = await start_league(guild_id, force_bot_fill=False)
                return result

            # Case 5: Deadline passed, enough humans, bot fill enabled
            if total_count < target_club_count and fill_bots_after_deadline:
                logger.info(f"lifecycle_check_start: Case 5 (bot fill) triggered for guild_id={guild_id}")
                result = await start_league(guild_id, force_bot_fill=True)
                return result

            # Case 6: Deadline passed, enough humans, bot fill disabled
            if total_count < target_club_count and not fill_bots_after_deadline:
                reason = "League is under-filled and bot filling is disabled."
                await LeagueLifecycleService.transition_to_review(league_id, reason, guild_id, joined_player_user_ids)
                return LeagueResult(success=False, code="needs_admin_review", message=reason, league_id=league_id, league_name=league_name)

            return None

        except Exception as e:
            logger.error(f"lifecycle_check_failed: error during check for guild_id={guild_id}: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return None

    @staticmethod
    async def transition_to_review(league_id, reason: str, guild_id: int | str, player_user_ids: list[str | int]) -> None:
        """
        Transition league to NEEDS_ADMIN_REVIEW status. Notify admin, notify joined players, and announce in channel.
        """
        try:
            async with get_session() as session:
                stmt = select(League).where(League.id == league_id).with_for_update()
                res = await session.execute(stmt)
                league = res.scalar_one_or_none()
                if league and league.status == LeagueStatus.DRAFT:
                    league.status = LeagueStatus.NEEDS_ADMIN_REVIEW
                    league.review_reason = reason
                    await session.commit()
                    logger.info(f"league_moved_to_review: league_id={league_id}, reason={reason}")
                    
                    # 1. Notify Guild Owner/Admin
                    admin_message = (
                        f"🛡️ **ElevenBoss Admin Alert**\n\n"
                        f"The league **{league.name}** in your server requires your review.\n"
                        f"**Reason:** {reason}\n\n"
                        f"Please DM me `/admin` and select the server to resolve this (Extend Deadline, Force Start, or Cancel)."
                    )
                    await AnnouncementService.notify_guild_admin_dm(guild_id, admin_message)

                    # 2. Notify Joined Players
                    player_message = (
                        f"⚠️ **League Registration Update**\n\n"
                        f"The league did not reach the required registration conditions before the deadline. "
                        f"An admin has been notified."
                    )
                    await AnnouncementService.notify_users_dm(player_user_ids, player_message)

                    # 3. Public Game Channel Announcement
                    public_message = (
                        f"⚠️ **League Registration Closed — Pending Admin Review**\n\n"
                        f"The registration deadline has passed but the league requires administrative review before starting. "
                        f"Server administrators have been notified."
                    )
                    await AnnouncementService.send_announcement(guild_id, public_message)
                else:
                    logger.warning(f"league_transition_to_review_skipped: league_id={league_id} not in DRAFT status")
        except Exception as e:
            logger.error(f"league_transition_to_review_failed: league_id={league_id}, error={e}", exc_info=e)

    @staticmethod
    async def complete_current_season(session: AsyncSession, guild_id: int | str, season_id: uuid.UUID) -> bool:
        """
        Finalizes the current season, transitions it to COMPLETED.
        If auto_start_league is enabled, automatically transitions it to ARCHIVED and bootstraps the next season.
        Uses explicit row locking and scheduler locks to prevent concurrency.
        """
        from app.models.season import Season, SeasonStatus
        from app.models.league import League, LeagueStatus
        from app.repositories import get_or_create_running_job, mark_job_success
        from app.repositories.guild_config_repository import get_or_create_guild_config
        
        # 1. Lock the Season row
        stmt = select(Season).where(Season.id == season_id).with_for_update()
        res = await session.execute(stmt)
        season = res.scalar_one_or_none()
        if not season or season.status != SeasonStatus.ACTIVE:
            logger.warning(f"complete_season_skipped: season_id={season_id} not active or not found")
            return False
            
        # 2. Lock the League row
        stmt = select(League).where(League.id == season.league_id).with_for_update()
        res = await session.execute(stmt)
        league = res.scalar_one_or_none()
        if not league:
            logger.warning(f"complete_season_failed: league not found for season_id={season_id}")
            return False

        job_key = f"season_advance:{guild_id}:{season_id}"
        try:
            await get_or_create_running_job(
                session=session,
                job_key=job_key,
                job_type="season_advance",
                guild_id=guild_id
            )
            await session.flush()
        except ValueError as ve:
            logger.info(f"complete_season_rejected: reason=already_advancing, job_key={job_key}")
            return False

        # Transition status to completed
        season.status = SeasonStatus.COMPLETED
        season.ended_at = datetime.utcnow()
        league.status = LeagueStatus.COMPLETED
        
        # Age players and handle growth / decline / retirement
        from app.services.player_service import PlayerService
        await PlayerService.age_players(season.id, session)
        
        await session.flush()

        # Check config for auto start
        config = await get_or_create_guild_config(session, guild_id)
        if config.auto_start_league:
            # Transition COMPLETED to ARCHIVED
            season.status = SeasonStatus.ARCHIVED
            
            # Bootstrap next season
            next_season_number = season.season_number + 1
            bootstrap_key = f"season_bootstrap:{guild_id}:{next_season_number}"
            try:
                await get_or_create_running_job(
                    session=session,
                    job_key=bootstrap_key,
                    job_type="season_bootstrap",
                    guild_id=guild_id
                )
                await session.flush()
            except ValueError as ve:
                logger.info(f"complete_season_failed: next season bootstrap already running/completed, key={bootstrap_key}")
                await mark_job_success(session, job_key)
                return True

            # Perform bootstrapping
            await LeagueLifecycleService._bootstrap_season_internal(session, guild_id, league, next_season_number)
            
            # Mark both locks success
            await mark_job_success(session, job_key)
            await mark_job_success(session, bootstrap_key)
        else:
            # Unconditionally mark the completion lock success so it doesn't dangle
            await mark_job_success(session, job_key)

        return True

    @staticmethod
    async def _bootstrap_season_internal(session: AsyncSession, guild_id: int | str, league: League, next_season_number: int) -> "Season":
        """
        Helper method to archive old active states, create a new Season record,
        associate all current league clubs, initialize new standings, and generate fixtures.
        """
        from app.repositories import create_season, bulk_create_fixtures
        from app.models.season import Season, SeasonStatus
        from app.models.fixture import Fixture, FixtureStatus
        from app.services.standings_service import initialize_standings
        from app.engine.fixture_generator import generate_round_robin_fixtures
        
        # 1. Create Season N+1
        new_season = await create_season(session, guild_id, league.id, next_season_number)
        await session.flush()
        
        # 2. Retrieve all clubs in the league
        clubs = await get_clubs_in_league(session, guild_id, league.id)
        
        # 3. Associate clubs with new season
        for club in clubs:
            club.season_id = new_season.id
            
        # 4. Initialize standings
        club_ids = [club.id for club in clubs]
        await initialize_standings(session, guild_id, new_season.id, club_ids)
        
        # 5. Generate and persist fixtures
        club_id_strings = [str(cid) for cid in club_ids]
        generated = generate_round_robin_fixtures(club_id_strings, double_round_robin=False)
        
        fixture_objects = [
            Fixture(
                guild_id=str(guild_id),
                season_id=new_season.id,
                week=f.week,
                home_club_id=uuid.UUID(f.home_club_id),
                away_club_id=uuid.UUID(f.away_club_id),
                status=FixtureStatus.SCHEDULED,
            )
            for f in generated
        ]
        await bulk_create_fixtures(session, fixture_objects)
        await session.flush()
        
        # 6. Set league and new season to active
        league.status = LeagueStatus.ACTIVE
        new_season.status = SeasonStatus.ACTIVE
        new_season.current_week = 1
        await session.flush()
        
        logger.info(f"season_bootstrapped_successfully: league_id={league.id}, season_number={next_season_number}")
        return new_season

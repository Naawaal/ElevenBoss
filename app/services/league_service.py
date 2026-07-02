import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_session
from app.repositories import (
    get_active_or_draft_league_by_guild,
    get_draft_league_by_guild,
    get_active_league_by_guild,
    get_non_terminal_league_by_guild,
    get_latest_league_for_update,
    claim_league_for_starting,
    get_active_season_for_league,
    create_league as db_create_league,
    set_league_status,
    count_league_clubs,
    get_user_club,
    get_clubs_in_league,
    assign_club_to_league,
    assign_club_to_season,
    create_season,
    get_latest_season_for_league,
    bulk_create_fixtures,
)
from app.repositories.manager_repository import get_manager_by_discord_id
from app.services.bot_club_service import generate_bot_clubs_for_league
from app.services.standings_service import initialize_standings
from app.services.announcement_service import AnnouncementService
from app.engine.fixture_generator import generate_round_robin_fixtures, expected_fixture_counts
from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.club import Club
from app.models.fixture import Fixture, FixtureStatus
from app.utils.timezone import parse_deadline_to_utc

logger = logging.getLogger("app.services.league_service")

@dataclass
class LeagueResult:
    success: bool
    code: str
    message: str
    league_id: uuid.UUID | None = None
    season_id: uuid.UUID | None = None
    league_name: str | None = None
    league_size: int | None = None
    human_clubs: int = 0
    bot_clubs: int = 0
    # Fixture stats — populated after /league start
    total_clubs: int = 0
    total_weeks: int = 0
    fixtures_per_week: int = 0
    total_fixtures: int = 0
    current_week: int = 1

@dataclass
class LeagueStatusResult:
    success: bool
    code: str
    message: str
    league_id: uuid.UUID | None = None
    league_name: str | None = None
    status: str | None = None
    league_size: int | None = None
    human_clubs: int = 0
    bot_clubs: int = 0
    season_number: int | None = None
    current_week: int | None = None
    clubs: list[dict] | None = None

def validate_league_name(name: str) -> str:
    """
    Validate and normalize the league name.
    Raises ValueError on validation failures.
    """
    if not name:
        raise ValueError("League name cannot be empty.")
        
    # Block mass mentions
    if "@everyone" in name or "@here" in name:
        raise ValueError("League name cannot contain mass mentions (@everyone/@here).")
        
    # Block URLs
    if re.search(r"https?://|www\.", name, re.IGNORECASE) or name.endswith(".com"):
        raise ValueError("League name cannot contain URLs.")
        
    # Normalize excessive whitespace
    normalized = " ".join(name.split())
    
    # Length check
    if len(normalized) < 3 or len(normalized) > 40:
        raise ValueError("League name must be between 3 and 40 characters.")
        
    # Pattern check: letters, numbers, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z0-9\s'\-]+$", normalized):
        raise ValueError("League name contains invalid characters. Only letters, numbers, spaces, hyphens, and apostrophes are allowed.")
        
    return normalized

async def create_league(
    guild_id: int | str,
    league_name: str,
    league_size: int,
    registration_deadline: str | None = None,
    registration_deadline_timezone: str = "Asia/Kathmandu",
    minimum_human_clubs: int = 2,
    auto_start_after_deadline: bool = True,
    fill_bots_after_deadline: bool = True,
) -> LeagueResult:
    """
    Validates and creates a new draft league.
    """
    logger.info(
        f"league_create_started: guild_id={guild_id}, league_name={league_name}, league_size={league_size}, "
        f"deadline={registration_deadline}, tz={registration_deadline_timezone}, min_human={minimum_human_clubs}"
    )
    
    # Validate league size
    if league_size not in (8, 10, 12, 16):
        logger.warning(f"league_create_failed: invalid league size {league_size} for guild_id={guild_id}")
        return LeagueResult(
            success=False,
            code="invalid_league_size",
            message="Invalid league size. Allowed sizes are 8, 10, 12, or 16."
        )
        
    # Validate minimum human clubs
    if minimum_human_clubs < 1 or minimum_human_clubs > league_size:
        logger.warning(f"league_create_failed: invalid minimum human clubs {minimum_human_clubs} for guild_id={guild_id}")
        return LeagueResult(
            success=False,
            code="invalid_minimum_human_clubs",
            message=f"Minimum human clubs must be between 1 and the league size ({league_size})."
        )
        
    # Parse and validate registration deadline
    registration_deadline_at = None
    if registration_deadline:
        try:
            registration_deadline_at = parse_deadline_to_utc(registration_deadline, registration_deadline_timezone)
            if registration_deadline_at <= datetime.now(timezone.utc):
                logger.warning(f"league_create_failed: deadline in past: {registration_deadline_at} for guild_id={guild_id}")
                return LeagueResult(
                    success=False,
                    code="invalid_deadline",
                    message="Registration deadline must be in the future."
                )
        except Exception as e:
            logger.warning(f"league_create_failed: deadline parse error: {e} for guild_id={guild_id}")
            return LeagueResult(
                success=False,
                code="invalid_deadline",
                message=str(e)
            )

    # Validate league name
    try:
        validated_name = validate_league_name(league_name)
    except ValueError as e:
        logger.info(f"league_create_failed: invalid league name for guild_id={guild_id}, reason={e}")
        return LeagueResult(
            success=False,
            code="invalid_league_name",
            message=str(e)
        )
        
    try:
        async with get_session() as session:
            # Check for existing non-terminal league
            existing = await get_non_terminal_league_by_guild(session, guild_id)
            if existing:
                logger.info(f"league_create_failed: non-terminal league exists for guild_id={guild_id}")
                return LeagueResult(
                    success=False,
                    code="league_exists",
                    message="An active or draft league already exists in this server."
                )
                
            league = await db_create_league(
                session=session,
                guild_id=guild_id,
                name=validated_name,
                max_clubs=league_size,
                registration_deadline_at=registration_deadline_at,
                registration_deadline_timezone=registration_deadline_timezone,
                auto_start_after_deadline=auto_start_after_deadline,
                fill_bots_after_deadline=fill_bots_after_deadline,
                minimum_human_clubs=minimum_human_clubs
            )
            await session.flush()
            
            logger.info(f"league_created: guild_id={guild_id}, league_id={league.id}, league_name={validated_name}")
            return LeagueResult(
                success=True,
                code="success",
                message=f"League '{validated_name}' successfully created in draft status!",
                league_id=league.id,
                league_name=validated_name,
                league_size=league_size
            )
            
    except Exception as e:
        logger.error(f"league_create_failed: unexpected database error: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return LeagueResult(
            success=False,
            code="database_error",
            message="An unexpected database error occurred while creating the league."
        )

async def join_league(
    guild_id: int | str,
    discord_user_id: int | str,
) -> LeagueResult:
    """
    Assigns a registered club to the guild's draft league with row locking protection.
    """
    logger.info(f"league_join_started: guild_id={guild_id}, user_id={discord_user_id}")
    
    try:
        async with get_session() as session:
            # 1. Fetch latest league FOR UPDATE to serialize operations
            league = await get_latest_league_for_update(session, guild_id)
            
            if not league:
                logger.info(f"league_join_failed: no league found for guild_id={guild_id}")
                return LeagueResult(
                    success=False,
                    code="league_not_found",
                    message="There is no active draft league open for joining in this server."
                )

            # Reject if not draft, or deadline has passed
            if league.status != LeagueStatus.DRAFT:
                logger.info(f"league_join_failed: league {league.id} status is {league.status}")
                return LeagueResult(
                    success=False,
                    code="registration_closed",
                    message="Registration for this league has closed. Please wait for the next league or contact an admin."
                )
                
            if league.registration_deadline_at is not None and datetime.now(timezone.utc) >= league.registration_deadline_at:
                logger.info(f"league_join_failed: deadline passed for league {league.id}")
                return LeagueResult(
                    success=False,
                    code="registration_closed",
                    message="Registration for this league has closed. Please wait for the next league or contact an admin."
                )

            # Check if user is registered and has a club
            manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if not manager or not manager.club_id:
                logger.info(f"league_join_failed: manager not registered for guild_id={guild_id}, user_id={discord_user_id}")
                return LeagueResult(
                    success=False,
                    code="not_registered",
                    message="You must register a club first using `/register` before joining the league."
                )
                
            club = await get_user_club(session, guild_id, discord_user_id)
            if not club:
                logger.info(f"league_join_failed: club not found for guild_id={guild_id}, user_id={discord_user_id}")
                return LeagueResult(
                    success=False,
                    code="not_registered",
                    message="Club not found. Please register first."
                )
                
            # Check if club is already assigned to a draft/active league (or starting/needs_admin_review)
            if club.league_id:
                stmt = select(League).where(League.id == club.league_id)
                res = await session.execute(stmt)
                current_league = res.scalar_one_or_none()
                if current_league and current_league.status in (LeagueStatus.DRAFT, LeagueStatus.STARTING, LeagueStatus.ACTIVE, LeagueStatus.NEEDS_ADMIN_REVIEW):
                    if current_league.id == league.id:
                        logger.info(f"league_join_failed: club {club.id} already joined current league {league.id}")
                        return LeagueResult(
                            success=False,
                            code="already_joined",
                            message="Your club has already joined this league."
                        )
                    else:
                        logger.info(f"league_join_failed: club {club.id} already in active/draft league {current_league.id}")
                        return LeagueResult(
                            success=False,
                            code="already_joined",
                            message=f"Your club is already assigned to another active or draft league: '{current_league.name}'."
                        )
                        
            # Check if league is full using target_club_count
            joined_count = await count_league_clubs(session, guild_id, league.id)
            if joined_count >= league.target_club_count:
                logger.info(f"league_join_failed: league {league.id} is full (count={joined_count})")
                return LeagueResult(
                    success=False,
                    code="league_full",
                    message="This league is already full."
                )
                
            # Assign club to league
            club.league_id = league.id
            await session.commit()
            
            logger.info(f"league_joined: guild_id={guild_id}, club_id={club.id}, league_id={league.id}")
            
            return LeagueResult(
                success=True,
                code="success",
                message=f"Your club '{club.name}' has successfully joined the league '{league.name}'!",
                league_id=league.id,
                league_name=league.name,
                league_size=league.target_club_count
            )
            
    except Exception as e:
        logger.error(f"league_join_failed: unexpected database error: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return LeagueResult(
            success=False,
            code="database_error",
            message="An unexpected database error occurred while joining the league."
        )

async def start_league(
    guild_id: int | str,
    force_bot_fill: bool = True
) -> LeagueResult:
    """
    Starts the league season in one atomic transaction using a guarded status update.
    """
    logger.info(f"league_start_started: guild_id={guild_id}")

    try:
        async with get_session() as session:
            # 1. Guarded update: draft/needs_admin_review -> starting
            league = await claim_league_for_starting(session, guild_id)
            
            if not league:
                # Check if already active
                active = await get_active_league_by_guild(session, guild_id)
                if active:
                    return LeagueResult(
                        success=False,
                        code="league_already_active",
                        message="This league has already started. Use `/fixtures view` to browse the fixture schedule.",
                    )
                return LeagueResult(
                    success=False,
                    code="league_not_found",
                    message="No draft or review league was found in this server to start.",
                )

            league_id = league.id
            league_name = league.name
            target_club_count = league.target_club_count
            fill_bots_after_deadline = league.fill_bots_after_deadline
            minimum_human_clubs = league.minimum_human_clubs

            # 2. Re-count clubs inside transaction
            stmt = select(Club).where(
                Club.guild_id == str(guild_id),
                Club.league_id == league_id,
                Club.is_bot_controlled == False
            )
            result = await session.execute(stmt)
            human_clubs = list(result.scalars().all())
            human_count = len(human_clubs)

            bot_clubs_needed = target_club_count - human_count
            if bot_clubs_needed < 0:
                logger.info(f"league_start_failed: too_many_clubs, human_count={human_count}, target={target_club_count}")
                raise ValueError("Joined human clubs exceed the league size limit.")

            # 3. Generate bot filler clubs if needed
            bot_clubs: list[Club] = []
            if bot_clubs_needed > 0:
                if fill_bots_after_deadline or force_bot_fill:
                    logger.info(f"bot_clubs_generation_started: count={bot_clubs_needed}")
                    bot_clubs = await generate_bot_clubs_for_league(
                        session,
                        guild_id=guild_id,
                        league_id=league_id,
                        season_id=None,
                        count=bot_clubs_needed,
                    )
                    await session.flush()
                else:
                    raise ValueError("League is under-filled and bot filling is disabled.")

            # 4. Create Season 1
            season = await create_season(session, guild_id, league_id, season_number=1)
            await session.flush()

            # 5. Assign all clubs to the season
            all_clubs = human_clubs + bot_clubs
            for club in all_clubs:
                club.season_id = season.id

            # 6. Initialize standings
            club_ids = [club.id for club in all_clubs]
            await initialize_standings(session, guild_id, season.id, club_ids)

            # 7. Generate fixtures
            club_id_strings = [str(c.id) for c in all_clubs]
            generated = generate_round_robin_fixtures(club_id_strings, double_round_robin=False)

            # 8. Persist fixtures
            fixture_objects = [
                Fixture(
                    guild_id=str(guild_id),
                    season_id=season.id,
                    week=f.week,
                    home_club_id=uuid.UUID(f.home_club_id),
                    away_club_id=uuid.UUID(f.away_club_id),
                    status=FixtureStatus.SCHEDULED,
                )
                for f in generated
            ]
            await bulk_create_fixtures(session, fixture_objects)
            await session.flush()

            # 9. Update statuses to active
            league.status = LeagueStatus.ACTIVE
            
            season.status = SeasonStatus.ACTIVE
            season.current_week = 1

            await session.commit()

            counts = expected_fixture_counts(len(all_clubs))
            logger.info(f"league_started_successfully: league_id={league_id}")
            return LeagueResult(
                success=True,
                code="success",
                message=f"League '{league_name}' has started!",
                league_id=league_id,
                season_id=season.id,
                league_name=league_name,
                league_size=target_club_count,
                human_clubs=human_count,
                bot_clubs=len(bot_clubs),
                total_clubs=len(all_clubs),
                total_weeks=counts["total_weeks"],
                fixtures_per_week=counts["fixtures_per_week"],
                total_fixtures=len(fixture_objects),
                current_week=1,
            )

    except Exception as e:
        logger.error(f"league_start_failed: error={e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return LeagueResult(
            success=False,
            code="database_error",
            message=f"Start league failed: {e}",
        )

async def get_league_status(
    guild_id: int | str,
) -> LeagueStatusResult:
    """
    Fetch status of the active or draft league in the guild.
    """
    try:
        async with get_session() as session:
            league = await get_active_or_draft_league_by_guild(session, guild_id)
            if not league:
                return LeagueStatusResult(
                    success=False,
                    code="league_not_found",
                    message="No active or draft league exists in this server."
                )
                
            # Count human vs bot clubs in the league
            clubs = await get_clubs_in_league(session, guild_id, league.id)
            human_count = sum(1 for c in clubs if not c.is_bot_controlled)
            bot_count = sum(1 for c in clubs if c.is_bot_controlled)
            
            season_number = None
            current_week = None
            
            if league.status == LeagueStatus.ACTIVE:
                season = await get_latest_season_for_league(session, league.id)
                if season:
                    season_number = season.season_number
                    current_week = season.current_week
                    
            return LeagueStatusResult(
                success=True,
                code="success",
                message="Status loaded successfully.",
                league_id=league.id,
                league_name=league.name,
                status=league.status.value,
                league_size=league.max_clubs,
                human_clubs=human_count,
                bot_clubs=bot_count,
                season_number=season_number,
                current_week=current_week,
                clubs=[{"name": c.name, "is_bot": c.is_bot_controlled} for c in clubs]
            )
    except Exception as e:
        logger.error(f"league_status_failed: database error: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return LeagueStatusResult(
            success=False,
            code="database_error",
            message="Failed to fetch league status from database."
        )

async def extend_deadline(
    guild_id: int | str,
    new_deadline_str: str,
    timezone_str: str = "Asia/Kathmandu"
) -> LeagueResult:
    """
    Extend the registration deadline for a league currently in NEEDS_ADMIN_REVIEW.
    """
    try:
        new_deadline_at = parse_deadline_to_utc(new_deadline_str, timezone_str)
        if new_deadline_at <= datetime.now(timezone.utc):
            return LeagueResult(success=False, code="invalid_deadline", message="New deadline must be in the future.")
        
        async with get_session() as session:
            # Fetch the league in needs_admin_review status
            stmt = select(League).where(
                League.guild_id == str(guild_id),
                League.status == LeagueStatus.NEEDS_ADMIN_REVIEW
            )
            res = await session.execute(stmt)
            league = res.scalar_one_or_none()
            
            if not league:
                return LeagueResult(
                    success=False,
                    code="league_not_found",
                    message="No league in 'needs_admin_review' status was found to extend."
                )
            
            league.status = LeagueStatus.DRAFT
            league.registration_deadline_at = new_deadline_at
            league.registration_deadline_timezone = timezone_str
            league.review_reason = None
            
            await session.commit()
            logger.info(f"league_deadline_extended: league_id={league.id}, new_deadline={new_deadline_at}")
            
            # Announce publicly in channel
            public_message = (
                f"⏳ **League Registration Extended!**\n\n"
                f"The registration deadline for league **{league.name}** has been extended to "
                f"`{new_deadline_str} ({timezone_str})`. Registration is open again! Run `/league join` to register."
            )
            await AnnouncementService.send_announcement(guild_id, public_message)
            
            return LeagueResult(
                success=True,
                code="success",
                message=f"Registration deadline successfully extended! League has returned to draft status.",
                league_id=league.id,
                league_name=league.name
            )
    except Exception as e:
        logger.error(f"failed_to_extend_deadline: {e}", exc_info=e)
        return LeagueResult(success=False, code="database_error", message=f"Failed to extend deadline: {e}")

async def cancel_league(
    guild_id: int | str
) -> LeagueResult:
    """
    Cancel the current league (draft, review, starting, or active).
    """
    try:
        async with get_session() as session:
            stmt = select(League).where(
                League.guild_id == str(guild_id),
                League.status.in_([
                    LeagueStatus.DRAFT, 
                    LeagueStatus.NEEDS_ADMIN_REVIEW,
                    LeagueStatus.ACTIVE,
                    LeagueStatus.STARTING
                ])
            )
            res = await session.execute(stmt)
            league = res.scalar_one_or_none()
            
            if not league:
                return LeagueResult(
                    success=False,
                    code="league_not_found",
                    message="No active, draft, or review league was found to cancel."
                )
            
            league.status = LeagueStatus.CANCELLED
            
            # Mark all active/draft seasons as completed
            from app.models.season import Season, SeasonStatus
            stmt_seasons = select(Season).where(
                Season.league_id == league.id,
                Season.status != SeasonStatus.COMPLETED
            )
            res_seasons = await session.execute(stmt_seasons)
            seasons = res_seasons.scalars().all()
            for s in seasons:
                s.status = SeasonStatus.COMPLETED
            
            # Fetch joined manager user IDs for player notifications
            from app.models.manager import Manager
            stmt_users = select(Manager.discord_user_id).join(Club, Manager.id == Club.manager_id).where(
                Club.league_id == league.id,
                Club.is_bot_controlled == False
            )
            res_users = await session.execute(stmt_users)
            player_ids = list(res_users.scalars().all())
            
            await session.commit()
            logger.info(f"league_cancelled: league_id={league.id}")
            
            # Send DM notifications to players
            player_message = (
                f"❌ **League Announcement**\n\n"
                f"The league **{league.name}** has been cancelled by an administrator. "
                f"Your registered club still exists and can join a future league."
            )
            await AnnouncementService.notify_users_dm(player_ids, player_message)
            
            # Send channel announcement
            public_message = (
                f"❌ **League Cancelled**\n\n"
                f"The league **{league.name}** has been cancelled by an administrator. "
                f"Registered clubs are preserved and can join future leagues."
            )
            await AnnouncementService.send_announcement(guild_id, public_message)
            
            return LeagueResult(
                success=True,
                code="success",
                message=f"League '{league.name}' has been successfully cancelled.",
                league_id=league.id,
                league_name=league.name
            )
    except Exception as e:
        logger.error(f"failed_to_cancel_league: {e}", exc_info=e)
        return LeagueResult(success=False, code="database_error", message=f"Failed to cancel league: {e}")

async def update_league_configuration(
    guild_id: int | str,
    target_club_count: int | None = None,
    minimum_human_clubs: int | None = None,
    auto_start_after_deadline: bool | None = None,
    fill_bots_after_deadline: bool | None = None
) -> LeagueResult:
    """
    Updates the league configuration with edit validation guards.
    """
    try:
        async with get_session() as session:
            league = await get_draft_league_by_guild(session, guild_id)
            if not league:
                return LeagueResult(success=False, code="league_not_found", message="No draft league found to configure.")
                
            if target_club_count is not None:
                if target_club_count not in (8, 10, 12, 16):
                    return LeagueResult(success=False, code="invalid_league_size", message="Invalid size. Must be 8, 10, 12, or 16.")
                joined_count = await count_league_clubs(session, guild_id, league.id)
                if target_club_count < joined_count:
                    return LeagueResult(success=False, code="invalid_target_club_count", message="Cannot set target club count below the number of currently joined clubs.")
                league.target_club_count = target_club_count
                league.max_clubs = target_club_count
                
            if minimum_human_clubs is not None:
                if minimum_human_clubs < 1 or minimum_human_clubs > league.target_club_count:
                    return LeagueResult(success=False, code="invalid_minimum_human_clubs", message=f"Minimum human clubs must be between 1 and {league.target_club_count}.")
                league.minimum_human_clubs = minimum_human_clubs
                
            if auto_start_after_deadline is not None:
                league.auto_start_after_deadline = auto_start_after_deadline
            if fill_bots_after_deadline is not None:
                league.fill_bots_after_deadline = fill_bots_after_deadline
                
            await session.commit()
            return LeagueResult(success=True, code="success", message="League configuration updated successfully.", league_id=league.id)
    except Exception as e:
        return LeagueResult(success=False, code="database_error", message=str(e))

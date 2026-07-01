import logging
import re
import uuid
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_session
from app.repositories import (
    get_active_or_draft_league_by_guild,
    get_draft_league_by_guild,
    create_league as db_create_league,
    set_league_status,
    count_league_clubs,
    get_user_club,
    get_clubs_in_league,
    assign_club_to_league,
    assign_club_to_season,
    create_season,
    get_latest_season_for_league
)
from app.repositories.manager_repository import get_manager_by_discord_id
from app.services.bot_club_service import generate_bot_clubs_for_league
from app.services.standings_service import initialize_standings
from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.club import Club

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
) -> LeagueResult:
    """
    Validates and creates a new draft league.
    """
    logger.info(f"league_create_started: guild_id={guild_id}, league_name={league_name}, league_size={league_size}")
    
    # Validate league size
    if league_size not in (8, 10, 12, 16):
        logger.warning(f"league_create_failed: invalid league size {league_size} for guild_id={guild_id}")
        return LeagueResult(
            success=False,
            code="invalid_league_size",
            message="Invalid league size. Allowed sizes are 8, 10, 12, or 16."
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
            # Check for existing draft/active league
            existing = await get_active_or_draft_league_by_guild(session, guild_id)
            if existing:
                logger.info(f"league_create_failed: active/draft league exists for guild_id={guild_id}")
                return LeagueResult(
                    success=False,
                    code="league_exists",
                    message="An active or draft league already exists in this server."
                )
                
            league = await db_create_league(session, guild_id, validated_name, league_size)
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
    Assigns a registered club to the guild's draft league.
    """
    logger.info(f"league_join_started: guild_id={guild_id}, user_id={discord_user_id}")
    
    try:
        async with get_session() as session:
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
                
            # Get draft league in guild
            league = await get_draft_league_by_guild(session, guild_id)
            if not league:
                logger.info(f"league_join_failed: no draft league in guild_id={guild_id}")
                return LeagueResult(
                    success=False,
                    code="league_not_found",
                    message="There is no active draft league open for joining in this server."
                )
                
            # Check if club is already assigned to a draft or active league
            if club.league_id:
                stmt = select(League).where(League.id == club.league_id)
                res = await session.execute(stmt)
                current_league = res.scalar_one_or_none()
                if current_league and current_league.status in (LeagueStatus.DRAFT, LeagueStatus.ACTIVE):
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
                        
            # Check if league is full
            joined_count = await count_league_clubs(session, guild_id, league.id)
            if joined_count >= league.max_clubs:
                logger.info(f"league_join_failed: league {league.id} is full (count={joined_count})")
                return LeagueResult(
                    success=False,
                    code="league_full",
                    message="This league is already full."
                )
                
            # Assign club to league
            club.league_id = league.id
            logger.info(f"league_joined: guild_id={guild_id}, club_id={club.id}, league_id={league.id}")
            
            return LeagueResult(
                success=True,
                code="success",
                message=f"Your club '{club.name}' has successfully joined the league '{league.name}'!",
                league_id=league.id,
                league_name=league.name,
                league_size=league.max_clubs
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
) -> LeagueResult:
    """
    Starts the league season: fills empty slots with bot clubs, bootstraps season,
    and initializes standings. Executed atomically.
    """
    logger.info(f"league_start_started: guild_id={guild_id}")
    
    try:
        # Atomic database transaction using get_session() context manager
        async with get_session() as session:
            # Retrieve draft league
            league = await get_draft_league_by_guild(session, guild_id)
            if not league:
                logger.info(f"league_start_failed: no draft league in guild_id={guild_id}")
                return LeagueResult(
                    success=False,
                    code="league_not_found",
                    message="No draft league was found in this server to start."
                )
                
            # Get joined human clubs
            stmt = select(Club).where(
                Club.guild_id == str(guild_id),
                Club.league_id == league.id,
                Club.is_bot_controlled == False
            )
            result = await session.execute(stmt)
            human_clubs = list(result.scalars().all())
            human_count = len(human_clubs)
            
            bot_clubs_needed = league.max_clubs - human_count
            if bot_clubs_needed < 0:
                logger.info(f"league_start_failed: joined clubs ({human_count}) exceed max size ({league.max_clubs})")
                return LeagueResult(
                    success=False,
                    code="league_full",
                    message="Joined human clubs exceed the league size limit."
                )
                
            # Create Season 1
            season = await create_season(session, guild_id, league.id, season_number=1)
            await session.flush()
            
            # Generate bot filler clubs
            bot_clubs = []
            if bot_clubs_needed > 0:
                bot_clubs = await generate_bot_clubs_for_league(
                    session,
                    guild_id=guild_id,
                    league_id=league.id,
                    season_id=season.id,
                    count=bot_clubs_needed
                )
                await session.flush()
                
            # Link human clubs to season
            for club in human_clubs:
                club.season_id = season.id
                
            # Initialize standings for all clubs
            all_clubs = human_clubs + bot_clubs
            club_ids = [club.id for club in all_clubs]
            await initialize_standings(session, guild_id, season.id, club_ids)
            
            # Update league status to ACTIVE
            league.status = LeagueStatus.ACTIVE
            
            logger.info(
                f"league_started: guild_id={guild_id}, league_id={league.id}, season_id={season.id}, "
                f"human_clubs={human_count}, bot_clubs={len(bot_clubs)}"
            )
            
            return LeagueResult(
                success=True,
                code="success",
                message=f"League '{league.name}' has started!",
                league_id=league.id,
                season_id=season.id,
                league_name=league.name,
                league_size=league.max_clubs,
                human_clubs=human_count,
                bot_clubs=len(bot_clubs)
            )
            
    except Exception as e:
        logger.error(f"league_start_failed: unexpected database error: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        return LeagueResult(
            success=False,
            code="database_error",
            message="An unexpected database error occurred during season bootstrap. Operation rolled back."
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

import logging
import re
import uuid
from dataclasses import dataclass
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, create_manager, get_club_by_name, create_club, bulk_create_players
from app.engine import generate_squad

logger = logging.getLogger("app.services.registration_service")

@dataclass
class RegistrationResult:
    success: bool
    message: str
    error_type: str | None = None
    manager_id: uuid.UUID | None = None
    club_id: uuid.UUID | None = None
    club_name: str | None = None
    squad_size: int = 0
    average_overall: float | None = None
    budget: int = 0

def validate_club_name(name: str) -> str:
    """
    Validate and normalize the club name.
    Raises ValueError on validation failures.
    """
    if not name:
        raise ValueError("Club name cannot be empty.")
        
    # Block mass mentions
    if "@everyone" in name or "@here" in name:
        raise ValueError("Club name cannot contain mass mentions (@everyone/@here).")
        
    # Block URLs
    if re.search(r"https?://|www\.", name, re.IGNORECASE) or name.endswith(".com"):
        raise ValueError("Club name cannot contain URLs.")
        
    # Normalize excessive whitespace (trim leading/trailing and collapse double spaces)
    normalized = " ".join(name.split())
    
    # Length check
    if len(normalized) < 3 or len(normalized) > 32:
        raise ValueError("Club name must be between 3 and 32 characters.")
        
    # Pattern check: letters, numbers, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z0-9\s'\-]+$", normalized):
        raise ValueError("Club name contains invalid characters. Only letters, numbers, spaces, hyphens, and apostrophes are allowed.")
        
    return normalized

async def register_club(
    guild_id: int | str,
    discord_user_id: int | str,
    club_name: str,
) -> RegistrationResult:
    """
    Service workflow for registering a user manager, club, and 25 procedural players.
    All operations are wrapped in a single database transaction.
    """
    logger.info(
        f"registration_started: guild_id={guild_id}, discord_user_id={discord_user_id}, input_club_name={club_name}"
    )
    
    try:
        validated_name = validate_club_name(club_name)
    except ValueError as e:
        logger.warning(
            f"invalid_club_name: guild_id={guild_id}, discord_user_id={discord_user_id}, name={club_name}, reason={str(e)}"
        )
        return RegistrationResult(success=False, message=str(e), error_type="invalid_club_name")

    try:
        async with get_session() as session:
            # Check for duplicate manager in this server
            existing_manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if existing_manager:
                logger.warning(
                    f"duplicate_registration_attempt: manager already exists for guild_id={guild_id}, discord_user_id={discord_user_id}"
                )
                return RegistrationResult(
                    success=False,
                    message="You are already registered as a manager in this server.",
                    error_type="already_registered"
                )
                
            # Check for duplicate club name in this server
            existing_club = await get_club_by_name(session, guild_id, validated_name)
            if existing_club:
                logger.warning(
                    f"duplicate_registration_attempt: club name taken for guild_id={guild_id}, club_name={validated_name}"
                )
                return RegistrationResult(
                    success=False,
                    message="This club name is already taken in this server.",
                    error_type="club_name_taken"
                )

            # Create Manager
            manager = await create_manager(session, guild_id, discord_user_id)
            await session.flush()

            # Create Club
            club = await create_club(session, guild_id, manager.id, validated_name)
            await session.flush()

            # Link Manager to Club
            manager.club_id = club.id

            # Procedural Squad Generation
            logger.info(f"squad_generation_started: guild_id={guild_id}, club_id={club.id}")
            players = generate_squad(str(guild_id), club.id)
            await bulk_create_players(session, players)
            logger.info(f"squad_generation_success: guild_id={guild_id}, club_id={club.id}, size={len(players)}")

            avg_ovr = sum(p.overall for p in players) / len(players)
            
            # Auto-join draft league logic
            from app.repositories.guild_config_repository import get_or_create_guild_config
            from app.repositories.league_repository import get_draft_league_by_guild, count_league_clubs
            
            auto_join_note = ""
            try:
                config = await get_or_create_guild_config(session, guild_id)
                if config.auto_join_draft_league:
                    draft_league = await get_draft_league_by_guild(session, guild_id)
                    if draft_league:
                        joined_count = await count_league_clubs(session, guild_id, draft_league.id)
                        if joined_count < draft_league.max_clubs:
                            club.league_id = draft_league.id
                            auto_join_note = " Joined draft league automatically."
                            logger.info(f"auto_join_success: club_id={club.id} automatically joined draft league={draft_league.id} in guild_id={guild_id}")
                        else:
                            auto_join_note = " Auto-join skipped: league is full."
                            logger.info(f"auto_join_skipped: draft league is full for guild_id={guild_id}")
            except Exception as e:
                logger.error(f"auto_join_failed: guild_id={guild_id}, error={e}", exc_info=e)
                auto_join_note = " Auto-join failed due to a system error."
            
            logger.info(
                f"registration_success: guild_id={guild_id}, discord_user_id={discord_user_id}, club_name={validated_name}"
            )
            return RegistrationResult(
                success=True,
                message=f"Registration successful!{auto_join_note}",
                manager_id=manager.id,
                club_id=club.id,
                club_name=validated_name,
                squad_size=len(players),
                average_overall=round(avg_ovr, 1),
                budget=club.budget
            )
            
    except Exception as e:
        logger.error(
            f"registration_failed: unexpected database error for guild_id={guild_id}, discord_user_id={discord_user_id}, error={str(e)}",
            exc_info=e
        )
        # Sentry integration
        from app.error_reporting import capture_exception
        capture_exception(e)
        
        return RegistrationResult(
            success=False,
            message="An unexpected error occurred while registering your club. Please try again later.",
            error_type="database_error"
        )

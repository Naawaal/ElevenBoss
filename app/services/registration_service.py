import logging
import re
import uuid
from dataclasses import dataclass
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, create_manager, get_club_by_name, create_club
from app.services.player_service import PlayerService

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
            squad_result = await PlayerService.create_squad(club.id, session)
            players = squad_result.players
            logger.info(f"squad_generation_success: guild_id={guild_id}, club_id={club.id}, size={len(players)}")

            avg_ovr = sum(p.overall for p in players) / len(players)
            
            logger.info(
                f"registration_success: guild_id={guild_id}, discord_user_id={discord_user_id}, club_name={validated_name}"
            )
            return RegistrationResult(
                success=True,
                message="Registration successful!",
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

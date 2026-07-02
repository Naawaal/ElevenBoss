import logging
import re
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, get_club_by_manager_id, get_players_by_club_id
from app.repositories.club_repository import (
    get_user_club as _get_user_club,
    get_club_by_normalized_name,
    create_club_no_commit as _create_club_no_commit,
)

logger = logging.getLogger("app.services.club_service")


class ClubNameError(ValueError):
    """Raised when a club name fails validation."""


class ClubNameTakenError(Exception):
    """Raised when the normalized club name already exists in the guild."""


class ClubService:
    """Static-method service that owns club creation and querying concerns."""

    # Validation rules from the spec (Milestone R6)
    _MAX_LEN = 40
    _MIN_LEN = 3
    _ALLOWED_PATTERN = re.compile(r"^[a-zA-Z0-9\s'\-\.]+$")
    _SYMBOL_ONLY = re.compile(r"^[\s'\-\.]+$")
    _URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
    _INVITE_PATTERN = re.compile(r"discord\.gg/", re.IGNORECASE)

    @staticmethod
    def normalize_club_name(raw: str) -> str:
        """
        Casefold, strip, and collapse internal whitespace.
        Used to compare two names for uniqueness.
        """
        return re.sub(r"\s+", " ", raw.strip()).casefold()

    @staticmethod
    def validate_club_name(raw: str) -> str:
        """
        Validate and return the display-form normalized name (strip + collapse spaces,
        NOT casefold — the returned value is the stored display name).
        Raises ClubNameError on any violation.
        """
        # Strip and collapse whitespace (display form)
        display = re.sub(r"\s+", " ", raw.strip())

        if not display:
            raise ClubNameError("Club name cannot be empty.")
        if "@everyone" in display or "@here" in display:
            raise ClubNameError("Club name cannot contain mass mentions (@everyone / @here).")
        if ClubService._URL_PATTERN.search(display):
            raise ClubNameError("Club name cannot contain URLs.")
        if ClubService._INVITE_PATTERN.search(display):
            raise ClubNameError("Club name cannot contain Discord invite links.")
        if len(display) < ClubService._MIN_LEN or len(display) > ClubService._MAX_LEN:
            raise ClubNameError(
                f"Club name must be between {ClubService._MIN_LEN} and "
                f"{ClubService._MAX_LEN} characters."
            )
        if not ClubService._ALLOWED_PATTERN.match(display):
            raise ClubNameError(
                "Club name contains invalid characters. "
                "Only letters, numbers, spaces, hyphens, apostrophes, and periods are allowed."
            )
        if ClubService._SYMBOL_ONLY.match(display):
            raise ClubNameError("Club name must contain at least one letter or number.")
        return display

    @staticmethod
    async def get_user_club(
        guild_id: int | str, owner_discord_id: int | str, session: AsyncSession
    ):
        """Return the Club owned by the Discord user in this guild, or None."""
        return await _get_user_club(session, guild_id, owner_discord_id)

    @staticmethod
    async def club_name_exists(
        guild_id: int | str, normalized_name: str, session: AsyncSession
    ) -> bool:
        """Return True if a club with this normalized name already exists in the guild."""
        club = await get_club_by_normalized_name(session, guild_id, normalized_name)
        return club is not None

    @staticmethod
    async def create_club_no_commit(
        name: str,
        guild_id: int | str,
        manager_id: uuid.UUID,
        session: AsyncSession,
    ):
        """
        Validate the name, normalize it, check uniqueness, and add the Club to the session
        WITHOUT committing. The caller must persist both club creation and any dependent
        state (e.g. onboarding_session.club_id) in the same transaction.

        Raises:
            ClubNameError: if name fails validation.
            ClubNameTakenError: if the normalized name already exists in this guild.
        """
        display_name = ClubService.validate_club_name(name)
        normalized = ClubService.normalize_club_name(display_name)

        if await ClubService.club_name_exists(guild_id, normalized, session):
            raise ClubNameTakenError(
                f"The club name '{display_name}' is already taken in this server."
            )

        return await _create_club_no_commit(
            session=session,
            guild_id=guild_id,
            manager_id=manager_id,
            name=display_name,
            normalized_name=normalized,
        )


# ── Backwards-compatible module-level function ───────────────────────────────

async def get_manager_club_summary(guild_id: int | str, discord_user_id: int | str) -> dict | None:
    """
    Returns a dictionary summarizing the club's status and key details for a manager.
    Returns None if the manager or club is not registered.
    """
    try:
        async with get_session() as session:
            manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
            if not manager:
                return None

            club_id = manager.club_id
            if not club_id:
                return None

            club = await get_club_by_manager_id(session, guild_id, manager.id)
            if not club:
                return None

            players = await get_players_by_club_id(session, club.id)
            squad_size = len(players)

            avg_ovr = round(sum(p.overall for p in players) / squad_size, 1) if squad_size > 0 else 0.0

            best_player = max(players, key=lambda p: p.overall) if squad_size > 0 else None
            highest_pot_player = max(players, key=lambda p: p.potential) if squad_size > 0 else None

            from sqlalchemy import select, func
            from app.models.league import League, LeagueStatus
            from app.models.club import Club
            from app.models.season import Season

            league_status_str = "No Active League"
            if club.league_id:
                res_league = await session.execute(select(League).where(League.id == club.league_id))
                league = res_league.scalar_one_or_none()
                if league:
                    if league.status == LeagueStatus.DRAFT:
                        res_count = await session.execute(
                            select(func.count(Club.id)).where(Club.league_id == league.id)
                        )
                        club_count = res_count.scalar() or 0
                        league_status_str = f"Draft Lobby: {league.name} ({club_count}/{league.max_clubs})"
                    elif league.status == LeagueStatus.ACTIVE:
                        if club.season_id:
                            res_season = await session.execute(
                                select(Season).where(Season.id == club.season_id)
                            )
                            season = res_season.scalar_one_or_none()
                            if season:
                                league_status_str = f"{league.name} (Season {season.season_number})"
                            else:
                                league_status_str = f"{league.name} (Active)"
                        else:
                            league_status_str = f"{league.name} (Active)"
                    elif league.status == LeagueStatus.COMPLETED:
                        league_status_str = f"{league.name} (Completed)"

            return {
                "club_id": str(club.id),
                "club_name": club.name,
                "budget": club.budget,
                "reputation": club.reputation,
                "stadium_capacity": club.stadium_capacity,
                "squad_size": squad_size,
                "average_overall": avg_ovr,
                "best_player_name": best_player.display_name if best_player else "N/A",
                "best_player_ovr": best_player.overall if best_player else 0,
                "highest_pot_name": highest_pot_player.display_name if highest_pot_player else "N/A",
                "highest_pot_val": highest_pot_player.potential if highest_pot_player else 0,
                "league_status": league_status_str,
                "next_suggested_action": "View your squad details or examine player stats.",
                "discord_user_id": str(discord_user_id),
                "guild_id": str(guild_id)
            }
    except Exception as e:
        logger.error(f"Failed to fetch club summary: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.repositories import create_initial_standing, get_table_for_active_season
from app.models.standing import LeagueStanding

logger = logging.getLogger("app.services.standings_service")

async def initialize_standings(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    club_ids: list[uuid.UUID],
) -> list[LeagueStanding]:
    """
    Create initial standing records with zeroed stats for a list of clubs.
    """
    standings = []
    for club_id in club_ids:
        standing = await create_initial_standing(session, guild_id, season_id, club_id)
        standings.append(standing)
        
    logger.info(
        f"standings_initialized: guild_id={guild_id}, season_id={season_id}, "
        f"club_count={len(club_ids)}"
    )
    return standings

async def get_table(guild_id: int | str) -> list[LeagueStanding]:
    """
    Fetch the standings table for the active season in the guild.
    """
    try:
        async with get_session() as session:
            table = await get_table_for_active_season(session, guild_id)
            return table
    except Exception as e:
        logger.error(f"Failed to fetch standings table: {e}", exc_info=e)
        from app.error_reporting import capture_exception
        capture_exception(e)
        raise e

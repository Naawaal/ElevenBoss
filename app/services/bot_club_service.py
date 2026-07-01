import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.club import Club
from app.repositories import create_bot_club
from app.engine.bot_club_generator import generate_bot_clubs_data
from app.engine.player_generator import generate_squad

logger = logging.getLogger("app.services.bot_club_service")

async def generate_bot_clubs_for_league(
    session: AsyncSession,
    guild_id: int | str,
    league_id: uuid.UUID,
    season_id: uuid.UUID,
    count: int,
) -> list[Club]:
    """
    Generate and persist bot-controlled filler clubs and their 25-player squads.
    """
    logger.info(
        f"bot_clubs_generation_started: guild_id={guild_id}, league_id={league_id}, "
        f"season_id={season_id}, count={count}"
    )
    
    # Get existing club names to ensure name uniqueness in the guild
    stmt = select(Club.name).where(Club.guild_id == str(guild_id))
    result = await session.execute(stmt)
    existing_names = set(result.scalars().all())
    
    bot_clubs_data = generate_bot_clubs_data(str(guild_id), count, existing_names)
    
    created_clubs = []
    for bot_data in bot_clubs_data:
        # Create bot club
        club = await create_bot_club(session, guild_id, league_id, season_id, bot_data)
        await session.flush()
        
        # Generate and save a balanced squad of 25 players
        players = generate_squad(str(guild_id), club.id)
        session.add_all(players)
        await session.flush()
        
        # Calculate overall rating
        avg_ovr = sum(p.overall for p in players) / len(players)
        club.overall_rating = int(avg_ovr)
        
        created_clubs.append(club)
        
    logger.info(
        f"bot_clubs_generation_success: guild_id={guild_id}, count={len(created_clubs)}"
    )
    return created_clubs

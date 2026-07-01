import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.player import Player

async def bulk_create_players(session: AsyncSession, players: list[Player]) -> None:
    """
    Bulk create player records in a single operation.
    """
    session.add_all(players)

async def get_players_by_club_id(session: AsyncSession, club_id: uuid.UUID) -> list[Player]:
    """
    Fetch all active (non-retired) players belonging to a club, ordered by position and overall.
    """
    stmt = select(Player).where(
        Player.club_id == club_id,
        Player.is_retired == False
    ).order_by(Player.overall.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_player_by_id(session: AsyncSession, player_id: uuid.UUID) -> Player | None:
    """
    Fetch a player by their ID.
    """
    stmt = select(Player).where(Player.id == player_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_players_by_name(session: AsyncSession, club_id: uuid.UUID, name_query: str) -> list[Player]:
    """
    Fetch players in a club whose display_name contains name_query (case-insensitive).
    """
    stmt = select(Player).where(
        Player.club_id == club_id,
        Player.is_retired == False,
        Player.display_name.ilike(f"%{name_query}%")
    ).order_by(Player.overall.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


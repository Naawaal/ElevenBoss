import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.club import Club

async def get_club_by_name(session: AsyncSession, guild_id: int | str, name: str) -> Club | None:
    """
    Fetch a club in a specific guild by its name (case-insensitive or exact matching).
    """
    stmt = select(Club).where(
        Club.guild_id == str(guild_id),
        Club.name == name
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def create_club(session: AsyncSession, guild_id: int | str, manager_id: uuid.UUID, name: str) -> Club:
    """
    Create a new Club record.
    """
    club = Club(
        guild_id=str(guild_id),
        manager_id=manager_id,
        name=name,
        budget=10000000,  # Default budget
        reputation=500,
        stadium_capacity=10000,
        is_bot_controlled=False
    )
    session.add(club)
    return club

async def get_club_by_manager_id(session: AsyncSession, guild_id: int | str, manager_id: uuid.UUID) -> Club | None:
    """
    Fetch a club in a specific guild by manager ID.
    """
    stmt = select(Club).where(
        Club.guild_id == str(guild_id),
        Club.manager_id == manager_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.manager import Manager

async def get_manager_by_discord_id(session: AsyncSession, guild_id: int | str, discord_user_id: int | str) -> Manager | None:
    """
    Fetch a manager in a specific guild by their Discord user ID.
    """
    stmt = select(Manager).where(
        Manager.guild_id == str(guild_id),
        Manager.discord_user_id == str(discord_user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def create_manager(session: AsyncSession, guild_id: int | str, discord_user_id: int | str) -> Manager:
    """
    Create a new Manager record in the database.
    """
    manager = Manager(
        guild_id=str(guild_id),
        discord_user_id=str(discord_user_id),
        reputation=100,
        coins=1000
    )
    session.add(manager)
    return manager

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.models.manager import Manager
from app.models.manager_xp_event import ManagerXPEvent

async def get_manager_by_club_id(session: AsyncSession, club_id: uuid.UUID) -> Manager | None:
    """
    Fetch a manager in a specific guild by their club ID.
    """
    stmt = select(Manager).where(Manager.club_id == club_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def insert_xp_event_if_new(
    session: AsyncSession,
    manager_id: uuid.UUID,
    guild_id: int | str,
    source_type: str,
    source_id: str,
    xp_amount: int,
    description: str | None = None,
) -> bool:
    """
    Inserts a new manager XP event into the database.
    Uses ON CONFLICT DO NOTHING to prevent transaction poisoning.
    Returns True if successfully inserted, False if it was a duplicate.
    """
    bind = session.bind
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = (
            pg_insert(ManagerXPEvent)
            .values(
                manager_id=manager_id,
                guild_id=str(guild_id),
                source_type=source_type,
                source_id=str(source_id),
                xp_amount=xp_amount,
                description=description
            )
            .on_conflict_do_nothing(constraint="uq_manager_xp_event_source")
            .returning(ManagerXPEvent.id)
        )
        res = await session.execute(stmt)
        inserted_id = res.scalar_one_or_none()
        return inserted_id is not None
    else:
        # SQLite dialect for tests
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = (
            sqlite_insert(ManagerXPEvent)
            .values(
                manager_id=manager_id,
                guild_id=str(guild_id),
                source_type=source_type,
                source_id=str(source_id),
                xp_amount=xp_amount,
                description=description
            )
            .on_conflict_do_nothing()
            .returning(ManagerXPEvent.id)
        )
        res = await session.execute(stmt)
        inserted_id = res.scalar_one_or_none()
        return inserted_id is not None

async def add_career_xp(session: AsyncSession, manager_id: uuid.UUID, xp_amount: int) -> None:
    """
    Atomically increments the manager's career XP by the given amount.
    """
    stmt = (
        update(Manager)
        .where(Manager.id == manager_id)
        .values(career_xp=Manager.career_xp + xp_amount)
    )
    await session.execute(stmt)

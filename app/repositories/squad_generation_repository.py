"""
Squad generation run repository — idempotency guards for PlayerService.create_squad().
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.squad_generation_run import SquadGenerationRun


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_generation_run(
    session: AsyncSession, club_id: uuid.UUID
) -> SquadGenerationRun | None:
    """Return the existing generation run for a club, if any."""
    stmt = select(SquadGenerationRun).where(SquadGenerationRun.club_id == club_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_generation_run(
    session: AsyncSession, club_id: uuid.UUID, generation_key: str
) -> SquadGenerationRun:
    """
    Insert a new IN_PROGRESS generation run.
    The unique constraint on (club_id) will raise IntegrityError if one already exists.
    """
    run = SquadGenerationRun(
        club_id=club_id,
        generation_key=generation_key,
        status="IN_PROGRESS",
        started_at=_now(),
    )
    session.add(run)
    await session.flush()
    return run


async def mark_run_complete(session: AsyncSession, club_id: uuid.UUID) -> None:
    """Mark the generation run for a club as COMPLETED."""
    stmt = (
        update(SquadGenerationRun)
        .where(SquadGenerationRun.club_id == club_id)
        .values(status="COMPLETED", completed_at=_now())
    )
    await session.execute(stmt)


async def mark_run_failed(session: AsyncSession, club_id: uuid.UUID) -> None:
    """Mark the generation run for a club as FAILED."""
    stmt = (
        update(SquadGenerationRun)
        .where(SquadGenerationRun.club_id == club_id)
        .values(status="FAILED")
    )
    await session.execute(stmt)


async def delete_run(session: AsyncSession, club_id: uuid.UUID) -> None:
    """Remove a generation run (e.g. before a repair/regenerate pass)."""
    run = await get_generation_run(session, club_id)
    if run:
        await session.delete(run)
        await session.flush()

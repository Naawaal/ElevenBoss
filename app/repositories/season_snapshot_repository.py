import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.season_snapshot import SeasonSnapshot

async def create_season_snapshot(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    league_id: uuid.UUID,
    season_number: int,
    champion_club_id: uuid.UUID | None,
    runner_up_club_id: uuid.UUID | None,
    final_table_json: dict,
    total_matches: int,
    total_goals: int,
    completed_at: datetime,
) -> SeasonSnapshot:
    """
    Creates and records a standings snapshot for a completed season.
    """
    snapshot = SeasonSnapshot(
        guild_id=str(guild_id),
        season_id=season_id,
        league_id=league_id,
        season_number=season_number,
        champion_club_id=champion_club_id,
        runner_up_club_id=runner_up_club_id,
        final_table_json=final_table_json,
        total_matches=total_matches,
        total_goals=total_goals,
        completed_at=completed_at,
    )
    session.add(snapshot)
    return snapshot

async def get_season_snapshot(
    session: AsyncSession,
    season_id: uuid.UUID
) -> SeasonSnapshot | None:
    """
    Retrieves the snapshot for a specific season ID.
    """
    stmt = select(SeasonSnapshot).where(SeasonSnapshot.season_id == season_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()

async def get_season_snapshot_by_number(
    session: AsyncSession,
    league_id: uuid.UUID,
    season_number: int
) -> SeasonSnapshot | None:
    """
    Retrieves the snapshot for a specific league and season number.
    """
    stmt = select(SeasonSnapshot).where(
        SeasonSnapshot.league_id == league_id,
        SeasonSnapshot.season_number == season_number
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()

async def list_season_snapshots_for_league(
    session: AsyncSession,
    league_id: uuid.UUID
) -> list[SeasonSnapshot]:
    """
    Lists all snapshots for a given league ordered by season number.
    """
    stmt = select(SeasonSnapshot).where(SeasonSnapshot.league_id == league_id).order_by(SeasonSnapshot.season_number.asc())
    res = await session.execute(stmt)
    return list(res.scalars().all())

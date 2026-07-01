"""
Fixture Repository — Database query logic for fixtures.

All queries filter by guild_id for multi-guild isolation.
All operations are async and use SQLAlchemy 2.0 patterns.
No business logic here — only raw data access.
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.fixture import Fixture, FixtureStatus


async def fixtures_exist_for_season(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
) -> bool:
    """
    Returns True if any fixtures have already been generated for this season in this guild.
    Used to prevent duplicate fixture generation.
    """
    stmt = select(func.count(Fixture.id)).where(
        Fixture.guild_id == str(guild_id),
        Fixture.season_id == season_id,
    )
    result = await session.execute(stmt)
    count = result.scalar() or 0
    return count > 0


async def bulk_create_fixtures(
    session: AsyncSession,
    fixtures: list[Fixture],
) -> list[Fixture]:
    """
    Bulk-inserts a list of Fixture ORM objects into the session.
    The caller is responsible for flushing and committing.
    """
    session.add_all(fixtures)
    return fixtures


async def get_fixtures_by_week(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    week: int,
) -> list[Fixture]:
    """
    Fetch all fixtures for a specific week in the active season.
    Results are ordered by week, then home_club_id for consistent display.
    """
    from sqlalchemy.orm import joinedload
    stmt = (
        select(Fixture)
        .options(
            joinedload(Fixture.home_club),
            joinedload(Fixture.away_club),
        )
        .where(
            Fixture.guild_id == str(guild_id),
            Fixture.season_id == season_id,
            Fixture.week == week,
        )
        .order_by(Fixture.week, Fixture.home_club_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())



async def get_fixtures_for_active_week(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    current_week: int,
) -> list[Fixture]:
    """
    Fetch all fixtures for the season's current (active) week.
    Delegates to get_fixtures_by_week for consistency.
    """
    return await get_fixtures_by_week(session, guild_id, season_id, current_week)


async def get_fixture_week_range(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
) -> tuple[int, int] | None:
    """
    Returns (min_week, max_week) for all fixtures in the season.
    Returns None if no fixtures exist yet.
    """
    stmt = select(
        func.min(Fixture.week),
        func.max(Fixture.week),
    ).where(
        Fixture.guild_id == str(guild_id),
        Fixture.season_id == season_id,
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None or row[0] is None:
        return None
    return (row[0], row[1])


async def count_fixtures_for_season(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
) -> int:
    """
    Count total fixtures persisted for a season.
    """
    stmt = select(func.count(Fixture.id)).where(
        Fixture.guild_id == str(guild_id),
        Fixture.season_id == season_id,
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_current_week_fixtures_for_update(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    week: int,
) -> list[Fixture]:
    """
    Fetch fixtures for the week with a write lock (FOR UPDATE).
    Eagerloads home_club and away_club relationships.
    """
    from sqlalchemy.orm import joinedload
    stmt = (
        select(Fixture)
        .options(
            joinedload(Fixture.home_club),
            joinedload(Fixture.away_club),
        )
        .where(
            Fixture.guild_id == str(guild_id),
            Fixture.season_id == season_id,
            Fixture.week == week,
        )
        .with_for_update(of=Fixture)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())





async def get_week_fixture_counts(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    week: int,
) -> dict:
    """
    Get count of scheduled vs played fixtures for the week.
    """
    stmt = select(Fixture.status, func.count(Fixture.id)).where(
        Fixture.guild_id == str(guild_id),
        Fixture.season_id == season_id,
        Fixture.week == week,
    ).group_by(Fixture.status)
    result = await session.execute(stmt)
    
    counts = {"total": 0, "scheduled": 0, "played": 0}
    for status, count in result.all():
        val = status.value if hasattr(status, "value") else str(status)
        counts[val] = count
        counts["total"] += count
    return counts


async def mark_fixture_played(
    session: AsyncSession,
    fixture_id: uuid.UUID,
    home_goals: int,
    away_goals: int,
    seed: str,
) -> None:
    """
    Mark a fixture as played and save goals/seed.
    """
    stmt = select(Fixture).where(Fixture.id == fixture_id)
    result = await session.execute(stmt)
    fixture = result.scalar_one_or_none()
    if fixture:
        fixture.status = FixtureStatus.PLAYED
        fixture.home_goals = home_goals
        fixture.away_goals = away_goals
        fixture.simulation_seed = seed
        from datetime import datetime
        fixture.played_at = datetime.utcnow()


async def get_latest_played_fixture(
    session: AsyncSession,
    guild_id: int | str,
) -> Fixture | None:
    """
    Get the most recently played fixture, eagerloading clubs.
    """
    from sqlalchemy.orm import joinedload
    stmt = (
        select(Fixture)
        .where(
            Fixture.guild_id == str(guild_id),
            Fixture.status == FixtureStatus.PLAYED
        )
        .options(
            joinedload(Fixture.home_club),
            joinedload(Fixture.away_club),
            joinedload(Fixture.match_result)
        )
        .order_by(Fixture.played_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


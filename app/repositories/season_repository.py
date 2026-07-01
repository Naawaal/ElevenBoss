import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.season import Season, SeasonStatus

async def get_latest_season_for_league(session: AsyncSession, league_id: uuid.UUID) -> Season | None:
    """
    Fetch the latest season for a given league, ordered by season number descending.
    """
    stmt = select(Season).where(
        Season.league_id == league_id
    ).order_by(Season.season_number.desc())
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_season(session: AsyncSession, guild_id: int | str, league_id: uuid.UUID, season_number: int) -> Season:
    """
    Create a new Season record.
    """
    season = Season(
        guild_id=str(guild_id),
        league_id=league_id,
        season_number=season_number,
        status=SeasonStatus.ACTIVE,  # Active by default on bootstrap
        current_week=1
    )
    session.add(season)
    return season

async def set_season_status(session: AsyncSession, season_id: uuid.UUID, status: SeasonStatus) -> None:
    """
    Update a season's status.
    """
    stmt = select(Season).where(Season.id == season_id)
    result = await session.execute(stmt)
    season = result.scalar_one_or_none()
    if season:
        season.status = status

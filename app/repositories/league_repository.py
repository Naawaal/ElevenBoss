import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.league import League, LeagueStatus
from app.models.club import Club

async def get_active_or_draft_league_by_guild(session: AsyncSession, guild_id: int | str) -> League | None:
    """
    Fetch the single active or draft league in a specific guild (only one active/draft league allowed per guild).
    """
    stmt = select(League).where(
        League.guild_id == str(guild_id),
        League.status.in_([LeagueStatus.DRAFT, LeagueStatus.ACTIVE])
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_draft_league_by_guild(session: AsyncSession, guild_id: int | str) -> League | None:
    """
    Fetch the draft league in a specific guild.
    """
    stmt = select(League).where(
        League.guild_id == str(guild_id),
        League.status == LeagueStatus.DRAFT
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def create_league(session: AsyncSession, guild_id: int | str, name: str, max_clubs: int) -> League:
    """
    Create a new draft League record.
    """
    league = League(
        guild_id=str(guild_id),
        name=name,
        max_clubs=max_clubs,
        status=LeagueStatus.DRAFT,
        tier=1
    )
    session.add(league)
    return league

async def set_league_status(session: AsyncSession, league_id: uuid.UUID, status: LeagueStatus) -> None:
    """
    Update a league's status.
    """
    stmt = select(League).where(League.id == league_id)
    result = await session.execute(stmt)
    league = result.scalar_one_or_none()
    if league:
        league.status = status

async def count_league_clubs(session: AsyncSession, guild_id: int | str, league_id: uuid.UUID) -> int:
    """
    Count the number of clubs assigned to a league in the guild.
    """
    stmt = select(func.count(Club.id)).where(
        Club.guild_id == str(guild_id),
        Club.league_id == league_id
    )
    result = await session.execute(stmt)
    return result.scalar() or 0

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from app.models.standing import LeagueStanding
from app.models.season import Season, SeasonStatus
from app.models.league import League, LeagueStatus
from app.models.club import Club

async def create_initial_standing(session: AsyncSession, guild_id: int | str, season_id: uuid.UUID, club_id: uuid.UUID) -> LeagueStanding:
    """
    Create a fresh LeagueStanding row for a club with 0 stats.
    """
    standing = LeagueStanding(
        guild_id=str(guild_id),
        season_id=season_id,
        club_id=club_id,
        played=0,
        wins=0,
        draws=0,
        losses=0,
        goals_for=0,
        goals_against=0,
        goal_difference=0,
        points=0
    )
    session.add(standing)
    return standing

async def get_table_for_active_season(session: AsyncSession, guild_id: int | str) -> list[LeagueStanding]:
    """
    Fetch all standing rows for the active season of the active league in the guild.
    Sorted by points (desc), goal_difference (desc), goals_for (desc), and club name (asc).
    """
    stmt = (
        select(LeagueStanding)
        .join(Club, LeagueStanding.club_id == Club.id)
        .join(Season, LeagueStanding.season_id == Season.id)
        .join(League, Season.league_id == League.id)
        .where(
            LeagueStanding.guild_id == str(guild_id),
            League.status == LeagueStatus.ACTIVE,
            Season.status == SeasonStatus.ACTIVE
        )
        .options(
            joinedload(LeagueStanding.club),
            joinedload(LeagueStanding.season).joinedload(Season.league)
        )
        .order_by(
            LeagueStanding.points.desc(),
            LeagueStanding.goal_difference.desc(),
            LeagueStanding.goals_for.desc(),
            Club.name.asc()
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_standing_for_update(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
    club_id: uuid.UUID
) -> LeagueStanding | None:
    """
    Fetch standing record for a club with a write lock (FOR UPDATE).
    """
    stmt = (
        select(LeagueStanding)
        .where(
            LeagueStanding.guild_id == str(guild_id),
            LeagueStanding.season_id == season_id,
            LeagueStanding.club_id == club_id
        )
        .with_for_update()
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_ranked_table(
    session: AsyncSession,
    guild_id: int | str,
    season_id: uuid.UUID,
) -> list[LeagueStanding]:
    """
    Fetch all standing rows for a specific season in the guild.
    Sorted by points (desc), goal_difference (desc), goals_for (desc), and club name (asc).
    """
    stmt = (
        select(LeagueStanding)
        .join(Club, LeagueStanding.club_id == Club.id)
        .where(
            LeagueStanding.guild_id == str(guild_id),
            LeagueStanding.season_id == season_id
        )
        .options(
            joinedload(LeagueStanding.club)
        )
        .order_by(
            LeagueStanding.points.desc(),
            LeagueStanding.goal_difference.desc(),
            LeagueStanding.goals_for.desc(),
            Club.name.asc()
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())



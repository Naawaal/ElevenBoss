import uuid
from datetime import datetime
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

async def get_active_league_by_guild(session: AsyncSession, guild_id: int | str) -> League | None:
    """
    Fetch the single ACTIVE league in a specific guild.
    Returns None if the league is still in draft, completed, or archived.
    Used by fixture service which requires a fully-started season.
    """
    stmt = select(League).where(
        League.guild_id == str(guild_id),
        League.status == LeagueStatus.ACTIVE
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_non_terminal_league_by_guild(session: AsyncSession, guild_id: int | str) -> League | None:
    """
    Fetch any league that is not completed or cancelled.
    """
    stmt = select(League).where(
        League.guild_id == str(guild_id),
        League.status.in_([
            LeagueStatus.DRAFT,
            LeagueStatus.STARTING,
            LeagueStatus.ACTIVE,
            LeagueStatus.NEEDS_ADMIN_REVIEW
        ])
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

async def create_league(
    session: AsyncSession,
    guild_id: int | str,
    name: str,
    max_clubs: int,
    registration_deadline_at: datetime | None = None,
    registration_deadline_timezone: str | None = None,
    auto_start_after_deadline: bool = True,
    fill_bots_after_deadline: bool = True,
    minimum_human_clubs: int = 2
) -> League:
    """
    Create a new draft League record with full configurations.
    """
    league = League(
        guild_id=str(guild_id),
        name=name,
        max_clubs=max_clubs,
        target_club_count=max_clubs,  # synchronize target_club_count and max_clubs
        status=LeagueStatus.DRAFT,
        tier=1,
        registration_deadline_at=registration_deadline_at,
        registration_deadline_timezone=registration_deadline_timezone,
        auto_start_after_deadline=auto_start_after_deadline,
        fill_bots_after_deadline=fill_bots_after_deadline,
        minimum_human_clubs=minimum_human_clubs
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

async def get_latest_league_for_update(session: AsyncSession, guild_id: int | str) -> League | None:
    """
    Fetch the latest league in the guild for update (with row locking).
    """
    stmt = select(League).where(League.guild_id == str(guild_id)).order_by(League.created_at.desc()).limit(1).with_for_update()
    res = await session.execute(stmt)
    return res.scalar_one_or_none()

async def claim_league_for_starting(session: AsyncSession, guild_id: int | str) -> League | None:
    """
    Lock and transition the league in draft or needs_admin_review status to starting.
    """
    stmt = select(League).where(
        League.guild_id == str(guild_id),
        League.status.in_([LeagueStatus.DRAFT, LeagueStatus.NEEDS_ADMIN_REVIEW])
    ).with_for_update()
    res = await session.execute(stmt)
    league = res.scalar_one_or_none()
    if league:
        league.status = LeagueStatus.STARTING
        league.review_reason = None
        await session.flush()
    return league

async def get_joined_player_user_ids(session: AsyncSession, league_id: uuid.UUID) -> list[int]:
    """
    Get discord user IDs of human players who have joined the league.
    """
    from app.models.manager import Manager
    stmt = select(Manager.discord_user_id).join(Club).where(
        Club.league_id == league_id,
        Club.is_bot_controlled == False
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())

async def get_league_by_name_and_guild(session: AsyncSession, name: str, guild_id: int | str) -> League | None:
    """
    Fetch any league in a specific guild by its name.
    """
    stmt = select(League).where(
        League.guild_id == str(guild_id),
        League.name == name
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


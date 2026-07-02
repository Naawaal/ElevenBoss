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

async def create_club(
    session: AsyncSession,
    guild_id: int | str,
    manager_id: uuid.UUID,
    name: str,
    normalized_name: str | None = None,
) -> Club:
    """
    Create a new Club record and add it to the session (does NOT flush/commit).
    """
    if normalized_name is None:
        import re
        normalized_name = re.sub(r"\s+", " ", name.strip()).casefold()
    club = Club(
        guild_id=str(guild_id),
        manager_id=manager_id,
        name=name,
        normalized_name=normalized_name,
        budget=10000000,  # Default budget
        reputation=500,
        stadium_capacity=10000,
        is_bot_controlled=False
    )
    session.add(club)
    return club


async def create_club_no_commit(
    session: AsyncSession,
    guild_id: int | str,
    manager_id: uuid.UUID,
    name: str,
    normalized_name: str,
) -> Club:
    """
    Create a new Club without flushing or committing.
    Club creation and any dependent state (e.g. onboarding_session.club_id)
    must be persisted in the SAME caller-owned transaction.
    """
    club = Club(
        guild_id=str(guild_id),
        manager_id=manager_id,
        name=name,
        normalized_name=normalized_name,
        budget=10000000,
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

async def get_user_club(session: AsyncSession, guild_id: int | str, discord_user_id: int | str) -> Club | None:
    """
    Fetch a club in a specific guild by manager's Discord user ID.
    """
    from app.models.manager import Manager
    stmt = select(Club).join(Manager, Club.id == Manager.club_id).where(
        Club.guild_id == str(guild_id),
        Manager.discord_user_id == str(discord_user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_club_by_normalized_name(
    session: AsyncSession, guild_id: int | str, normalized_name: str
) -> Club | None:
    """
    Fetch a club by its casefold-normalized name (for uniqueness checks).
    """
    stmt = select(Club).where(
        Club.guild_id == str(guild_id),
        Club.normalized_name == normalized_name,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_clubs_in_league(session: AsyncSession, guild_id: int | str, league_id: uuid.UUID) -> list[Club]:
    """
    Fetch all clubs in a league within a specific guild.
    """
    stmt = select(Club).where(
        Club.guild_id == str(guild_id),
        Club.league_id == league_id
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def assign_club_to_league(session: AsyncSession, guild_id: int | str, club_id: uuid.UUID, league_id: uuid.UUID | None) -> None:
    """
    Update the club's league_id.
    """
    stmt = select(Club).where(
        Club.guild_id == str(guild_id),
        Club.id == club_id
    )
    result = await session.execute(stmt)
    club = result.scalar_one_or_none()
    if club:
        club.league_id = league_id

async def assign_club_to_season(session: AsyncSession, guild_id: int | str, club_id: uuid.UUID, season_id: uuid.UUID | None) -> None:
    """
    Update the club's season_id.
    """
    stmt = select(Club).where(
        Club.guild_id == str(guild_id),
        Club.id == club_id
    )
    result = await session.execute(stmt)
    club = result.scalar_one_or_none()
    if club:
        club.season_id = season_id

async def create_bot_club(
    session: AsyncSession,
    guild_id: int | str,
    league_id: uuid.UUID,
    season_id: uuid.UUID,
    generated_club
) -> Club:
    """
    Create a new bot club in the database.
    """
    import re
    normalized = re.sub(r"\s+", " ", generated_club.name.strip()).casefold()
    club = Club(
        guild_id=str(guild_id),
        league_id=league_id,
        season_id=season_id,
        manager_id=None,
        name=generated_club.name,
        normalized_name=normalized,
        short_name=generated_club.short_name,
        budget=generated_club.budget,
        reputation=generated_club.reputation,
        stadium_capacity=generated_club.stadium_capacity,
        is_bot_controlled=True
    )
    session.add(club)
    return club

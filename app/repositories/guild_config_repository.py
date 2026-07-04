# app/repositories/guild_config_repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.guild_config import GuildConfig
from datetime import datetime

async def get_or_create_guild_config(
    session: AsyncSession,
    guild_id: int | str
) -> GuildConfig:
    """
    Fetch the configuration row for a specific guild.
    If none exists, creates it with default settings.
    """
    stmt = select(GuildConfig).where(GuildConfig.guild_id == str(guild_id))
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    
    if not config:
        config = GuildConfig(
            guild_id=str(guild_id),
            auto_join_draft_league=True,
            auto_start_league=False,
            auto_fill_with_bot_clubs=True,
            minimum_human_clubs=2,
            matchday_enabled=False,
            matchday_timezone="Asia/Kathmandu"
        )
        session.add(config)
        await session.flush()
        
    return config

async def get_or_create_config(session: AsyncSession, guild_id: int | str) -> GuildConfig:
    """Alias for get_or_create_guild_config."""
    return await get_or_create_guild_config(session, guild_id)

async def update_channels(
    session: AsyncSession,
    guild_id: int | str,
    game_channel_id: str | None = None,
    matchday_channel_id: str | None = None
) -> None:
    config = await get_or_create_guild_config(session, guild_id)
    if game_channel_id is not None:
        config.game_channel_id = game_channel_id
    if matchday_channel_id is not None:
        config.matchday_announcement_channel_id = matchday_channel_id

async def update_admin_role(
    session: AsyncSession,
    guild_id: int | str,
    role_id: str | None
) -> None:
    config = await get_or_create_guild_config(session, guild_id)
    config.admin_role_id = role_id

async def update_automation_settings(
    session: AsyncSession,
    guild_id: int | str,
    auto_join: bool | None = None,
    auto_start: bool | None = None,
    auto_fill: bool | None = None,
    min_human: int | None = None,
    deadline: datetime | None = None
) -> None:
    config = await get_or_create_guild_config(session, guild_id)
    if auto_join is not None:
        config.auto_join_draft_league = auto_join
    if auto_start is not None:
        config.auto_start_league = auto_start
    if auto_fill is not None:
        config.auto_fill_with_bot_clubs = auto_fill
    if min_human is not None:
        config.minimum_human_clubs = min_human
    if deadline is not None:
        config.registration_deadline = deadline

async def update_schedule_settings(
    session: AsyncSession,
    guild_id: int | str,
    day: str | None = None,
    time: str | None = None,
    timezone: str | None = None,
    channel_id: str | None = None
) -> None:
    config = await get_or_create_guild_config(session, guild_id)
    if day is not None:
        config.matchday_day = day
    if time is not None:
        config.matchday_time = time
    if timezone is not None:
        config.matchday_timezone = timezone
    if channel_id is not None:
        config.matchday_announcement_channel_id = channel_id

async def set_matchday_enabled(
    session: AsyncSession,
    guild_id: int | str,
    enabled: bool
) -> None:
    config = await get_or_create_guild_config(session, guild_id)
    config.matchday_enabled = enabled

async def update_mention_role(
    session: AsyncSession,
    guild_id: int | str,
    role_id: str | None
) -> None:
    config = await get_or_create_guild_config(session, guild_id)
    config.mention_role_id = role_id

async def get_settings_overview(session: AsyncSession, guild_id: int | str) -> GuildConfig:
    return await get_or_create_guild_config(session, guild_id)

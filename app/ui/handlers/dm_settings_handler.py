# app/ui/handlers/dm_settings_handler.py

import logging
from datetime import datetime, timedelta
import discord
from sqlalchemy.future import select

from app.db.session import get_session
from app.repositories.guild_config_repository import get_or_create_guild_config
from app.repositories.league_repository import get_active_league_by_guild
from app.repositories.season_repository import get_active_season_for_league
from app.models.fixture import Fixture, FixtureStatus
from app.services.league_service import get_league_status
from app.services.schedule_service import ScheduleService
from app.services.permission_service import can_manage_guild_settings, can_manage_admin_role as can_manage_role_check
from app.services import permission_service
from app.services.guild_selection_service import GuildSelectionService
from app.ui.handlers.session import ui_session_manager

# Renderers
from app.ui.renderers.dm_settings_renderer import (
    render_dm_server_picker,
    render_settings_overview,
    render_settings_channels,
    render_settings_admin_role,
    render_settings_automation,
    render_settings_schedule,
    render_settings_matchday,
)

logger = logging.getLogger("app.ui.handlers.dm_settings_handler")

async def get_settings_helpers(guild_id: int):
    league_res = await get_league_status(guild_id)
    league_status = "N/A"
    season_week = "N/A"
    
    if league_res.success:
        league_status = league_res.status.upper() if league_res.status else "DRAFT"
        if league_res.status == "active":
            season_week = f"Season {league_res.season_number or 1} / Week {league_res.current_week or 1}"
        else:
            season_week = "Not Started"

    return league_status, season_week

async def get_next_run_string(config) -> str:
    next_run_str = "Disabled"
    if config.matchday_enabled and config.matchday_day and config.matchday_time:
        now_utc = datetime.utcnow()
        last_occ = ScheduleService.get_last_scheduled_occurrence(config, now_utc)
        if last_occ:
            next_occ = last_occ + timedelta(days=7)
            next_run_str = f"{next_occ.strftime('%Y-%m-%d %H:%M')} UTC"
    return next_run_str

async def handle_open_settings_console(user: discord.User | discord.Member, nonce: str | None = None):
    """
    Starts settings console. Resolves manageable guilds, skips to overview if 1.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
        session = ui_session_manager.get_session(nonce)
    else:
        # Create temporary session with guild_id=0
        session = ui_session_manager.create_session(user.id, 0)
        nonce = session.session_id

    views = await GuildSelectionService.get_manageable_guilds(user.id)
    if not views:
        logger.info(f"dm_settings_no_manageable_guilds: user_id={user.id}")
        # Clean up session
        ui_session_manager._sessions.pop(nonce, None)
        raise ValueError("You do not have permission to manage any ElevenBoss servers.")

    if len(views) == 1:
        # Skip server picker, update session guild_id directly
        session.guild_id = views[0].guild_id
        return await handle_open_settings_overview(views[0].guild_id, user, nonce)
        
    return render_dm_server_picker(views, nonce)

async def handle_open_settings_overview(guild_id: int, user: discord.User | discord.Member, nonce: str):
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    # Revalidate
    is_admin = await can_manage_guild_settings(guild_id, user.id)
    if not is_admin:
        raise ValueError("You do not have permission to manage settings for this server.")

    # Update session guild_id to bind it
    session = ui_session_manager.get_session(nonce)
    if session:
        session.guild_id = guild_id

    bot_obj = permission_service.bot
    guild_name = "ElevenBoss Server"
    guild = None
    if bot_obj:
        guild = bot_obj.get_guild(guild_id)
        if guild:
            guild_name = guild.name

    league_status, season_week = await get_settings_helpers(guild_id)

    async with get_session() as db_session:
        config = await get_or_create_guild_config(db_session, guild_id)
        next_run_str = await get_next_run_string(config)
        
        admin_role_name = "None"
        mention_role_name = "None"
        if guild:
            if config.admin_role_id:
                r = guild.get_role(int(config.admin_role_id))
                admin_role_name = f"@{r.name}" if r else f"ID: {config.admin_role_id}"
            if config.mention_role_id:
                r = guild.get_role(int(config.mention_role_id))
                mention_role_name = f"@{r.name}" if r else f"ID: {config.mention_role_id}"

        logger.info(f"dm_settings_panel_rendered: guild_id={guild_id}, user_id={user.id}")
        return render_settings_overview(config, guild_name, league_status, season_week, next_run_str, admin_role_name, mention_role_name, nonce, is_admin)

async def handle_open_settings_channels(guild_id: int, user: discord.User | discord.Member, nonce: str):
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_guild_settings(guild_id, user.id)
    if not is_admin:
        raise ValueError("Permission denied.")

    bot_obj = permission_service.bot
    guild_name = "ElevenBoss Server"
    guild_channels = []
    if bot_obj:
        guild = bot_obj.get_guild(guild_id)
        if guild:
            guild_name = guild.name
            guild_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]

    async with get_session() as db_session:
        config = await get_or_create_guild_config(db_session, guild_id)
        logger.info(f"dm_settings_channels_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_channels(config, guild_name, guild_channels, nonce, is_admin)

async def handle_open_settings_admin_role(guild_id: int, user: discord.User | discord.Member, nonce: str):
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    # Note that managing the admin role itself requires Discord Administrator
    is_discord_admin = await can_manage_role_check(guild_id, user.id)

    bot_obj = permission_service.bot
    guild_name = "ElevenBoss Server"
    guild_roles = []
    if bot_obj:
        guild = bot_obj.get_guild(guild_id)
        if guild:
            guild_name = guild.name
            guild_roles = [r for r in guild.roles if not r.is_default() and not r.managed]

    async with get_session() as db_session:
        config = await get_or_create_guild_config(db_session, guild_id)
        logger.info(f"dm_settings_admin_role_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_admin_role(config, guild_name, guild_roles, nonce, is_discord_admin)

async def handle_open_settings_automation(guild_id: int, user: discord.User | discord.Member, nonce: str):
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_guild_settings(guild_id, user.id)
    if not is_admin:
        raise ValueError("Permission denied.")

    bot_obj = permission_service.bot
    guild_name = "ElevenBoss Server"
    if bot_obj:
        guild = bot_obj.get_guild(guild_id)
        if guild:
            guild_name = guild.name

    async with get_session() as db_session:
        config = await get_or_create_guild_config(db_session, guild_id)
        logger.info(f"dm_settings_automation_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_automation(config, guild_name, nonce, is_admin)

async def handle_open_settings_schedule(guild_id: int, user: discord.User | discord.Member, nonce: str):
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_guild_settings(guild_id, user.id)
    if not is_admin:
        raise ValueError("Permission denied.")

    bot_obj = permission_service.bot
    guild_name = "ElevenBoss Server"
    if bot_obj:
        guild = bot_obj.get_guild(guild_id)
        if guild:
            guild_name = guild.name

    async with get_session() as db_session:
        config = await get_or_create_guild_config(db_session, guild_id)
        next_run_str = await get_next_run_string(config)
        logger.info(f"dm_settings_schedule_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_schedule(config, guild_name, next_run_str, nonce, is_admin)

async def handle_open_settings_matchday(guild_id: int, user: discord.User | discord.Member, nonce: str):
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_guild_settings(guild_id, user.id)
    if not is_admin:
        raise ValueError("Permission denied.")

    bot_obj = permission_service.bot
    guild_name = "ElevenBoss Server"
    if bot_obj:
        guild = bot_obj.get_guild(guild_id)
        if guild:
            guild_name = guild.name

    league_status, season_week = await get_settings_helpers(guild_id)
    fixtures_stats = {"total": 0, "scheduled": 0, "played": 0}

    async with get_session() as db_session:
        config = await get_or_create_guild_config(db_session, guild_id)
        league = await get_active_league_by_guild(db_session, guild_id)
        if league:
            season = await get_active_season_for_league(db_session, guild_id, league.id)
            if season:
                stmt = select(Fixture).where(Fixture.season_id == season.id)
                res = await db_session.execute(stmt)
                fixtures = res.scalars().all()
                fixtures_stats["total"] = len(fixtures)
                fixtures_stats["played"] = sum(1 for f in fixtures if f.status == FixtureStatus.PLAYED)
                fixtures_stats["scheduled"] = fixtures_stats["total"] - fixtures_stats["played"]

        logger.info(f"dm_settings_matchday_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_matchday(config, guild_name, league_status, season_week, fixtures_stats, nonce, is_admin)

# app/ui/handlers/settings_handler.py

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
from app.services.permission_service import can_manage_settings
from app.ui.handlers.session import ui_session_manager

# Renderers
from app.ui.renderers.settings_renderer import (
    render_settings_overview,
    render_settings_channels,
    render_settings_admin_role,
    render_settings_automation,
    render_settings_schedule,
    render_settings_matchday,
)

logger = logging.getLogger("app.ui.handlers.settings_handler")

async def get_settings_helpers(guild_id: int):
    """
    Helper to fetch league status, season week description, and next run details.
    """
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
    """
    Calculates next scheduled automation run time string.
    """
    next_run_str = "Disabled"
    if config.matchday_enabled and config.matchday_day and config.matchday_time:
        now_utc = datetime.utcnow()
        last_occ = ScheduleService.get_last_scheduled_occurrence(config, now_utc)
        if last_occ:
            next_occ = last_occ + timedelta(days=7)
            next_run_str = f"{next_occ.strftime('%Y-%m-%d %H:%M')} UTC"
    return next_run_str

async def handle_open_settings_overview(guild_id: int, user: discord.Member, nonce: str | None = None):
    """
    Renders the Settings Overview dashboard.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
    else:
        session = ui_session_manager.create_session(user.id, guild_id)
        nonce = session.session_id

    is_admin = await can_manage_settings(guild_id, user)
    league_status, season_week = await get_settings_helpers(guild_id)

    async with get_session() as session:
        config = await get_or_create_guild_config(session, guild_id)
        next_run_str = await get_next_run_string(config)
        logger.info(f"settings_overview_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_overview(config, league_status, season_week, next_run_str, nonce, is_admin)

async def handle_open_settings_channels(guild_id: int, user: discord.Member, nonce: str):
    """
    Renders the Channels configuration sub-dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_settings(guild_id, user)
    async with get_session() as session:
        config = await get_or_create_guild_config(session, guild_id)
        logger.info(f"settings_channels_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_channels(config, nonce, is_admin)

async def handle_open_settings_admin_role(guild_id: int, user: discord.Member, nonce: str):
    """
    Renders the Admin Role configuration sub-dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_settings(guild_id, user)
    async with get_session() as session:
        config = await get_or_create_guild_config(session, guild_id)
        logger.info(f"settings_admin_role_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_admin_role(config, nonce, is_admin)

async def handle_open_settings_automation(guild_id: int, user: discord.Member, nonce: str):
    """
    Renders the Automation configuration sub-dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_settings(guild_id, user)
    async with get_session() as session:
        config = await get_or_create_guild_config(session, guild_id)
        logger.info(f"settings_automation_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_automation(config, nonce, is_admin)

async def handle_open_settings_schedule(guild_id: int, user: discord.Member, nonce: str):
    """
    Renders the Schedule configuration sub-dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_settings(guild_id, user)
    async with get_session() as session:
        config = await get_or_create_guild_config(session, guild_id)
        next_run_str = await get_next_run_string(config)
        logger.info(f"settings_schedule_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_schedule(config, next_run_str, nonce, is_admin)

async def handle_open_settings_matchday(guild_id: int, user: discord.Member, nonce: str):
    """
    Renders the Matchday automation state sub-dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    is_admin = await can_manage_settings(guild_id, user)
    league_status, season_week = await get_settings_helpers(guild_id)
    
    fixtures_stats = {"total": 0, "scheduled": 0, "played": 0}
    
    async with get_session() as session:
        config = await get_or_create_guild_config(session, guild_id)
        league = await get_active_league_by_guild(session, guild_id)
        if league:
            season = await get_active_season_for_league(session, guild_id, league.id)
            if season:
                stmt = select(Fixture).where(Fixture.season_id == season.id)
                res = await session.execute(stmt)
                fixtures = res.scalars().all()
                fixtures_stats["total"] = len(fixtures)
                fixtures_stats["played"] = sum(1 for f in fixtures if f.status == FixtureStatus.PLAYED)
                fixtures_stats["scheduled"] = fixtures_stats["total"] - fixtures_stats["played"]
                
        logger.info(f"settings_matchday_viewed: guild_id={guild_id}, user_id={user.id}")
        return render_settings_matchday(config, league_status, season_week, fixtures_stats, nonce, is_admin)

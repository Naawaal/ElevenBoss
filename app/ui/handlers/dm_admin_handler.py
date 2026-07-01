# app/ui/handlers/dm_admin_handler.py

import logging
import discord

from app.services.permission_service import can_run_admin_action, bot as bot_ref
from app.ui.handlers.session import ui_session_manager
from app.ui.handlers.dm_settings_handler import get_settings_helpers
from app.ui.renderers.dm_admin_renderer import render_admin_dashboard
from app.services.guild_selection_service import GuildSelectionService
from app.ui.renderers.dm_settings_renderer import render_dm_server_picker

logger = logging.getLogger("app.ui.handlers.dm_admin_handler")

async def handle_open_admin_console(user: discord.User | discord.Member, nonce: str | None = None):
    """
    Initializes the admin panel session. Shows guild picker or skips if 1.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
        session = ui_session_manager.get_session(nonce)
    else:
        # Create a session and set destination to 'admin'
        session = ui_session_manager.create_session(user.id, 0, metadata={"dest": "admin"})
        nonce = session.session_id

    # Make sure we set the dest metadata
    session.metadata["dest"] = "admin"

    views = await GuildSelectionService.get_manageable_guilds(user.id)
    if not views:
        logger.info(f"dm_admin_no_manageable_guilds: user_id={user.id}")
        ui_session_manager._sessions.pop(nonce, None)
        raise ValueError("You do not have permission to manage any ElevenBoss servers.")

    if len(views) == 1:
        session.guild_id = views[0].guild_id
        return await handle_open_admin_dashboard(views[0].guild_id, user, nonce)
        
    return render_dm_server_picker(views, nonce)

async def handle_open_admin_dashboard(guild_id: int, user: discord.User | discord.Member, nonce: str):
    """
    Renders the admin override dashboard for a specific selected guild.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    # Revalidate
    is_admin = await can_run_admin_action(guild_id, user.id)
    if not is_admin:
        raise ValueError("You do not have permission to manage settings for this server.")

    # Update session guild_id to bind it
    session = ui_session_manager.get_session(nonce)
    if session:
        session.guild_id = guild_id

    guild_name = "ElevenBoss Server"
    if bot_ref:
        guild = bot_ref.get_guild(guild_id)
        if guild:
            guild_name = guild.name

    league_status, season_week = await get_settings_helpers(guild_id)
    
    logger.info(f"dm_admin_opened: guild_id={guild_id}, user_id={user.id}")
    return render_admin_dashboard(guild_name, league_status, season_week, is_admin, nonce)

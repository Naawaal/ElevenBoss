# app/ui/handlers/admin_handler.py

import logging
import discord

from app.services.permission_service import can_run_admin_action
from app.ui.handlers.session import ui_session_manager
from app.ui.handlers.settings_handler import get_settings_helpers
from app.ui.renderers.admin_renderer import render_admin_dashboard

logger = logging.getLogger("app.ui.handlers.admin_handler")

async def handle_open_admin_dashboard(guild_id: int, user: discord.Member, nonce: str | None = None):
    """
    Validates session/permissions and returns the Admin Override Dashboard.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
    else:
        session = ui_session_manager.create_session(user.id, guild_id)
        nonce = session.session_id

    is_admin = await can_run_admin_action(guild_id, user)
    league_status, season_week = await get_settings_helpers(guild_id)
    
    return render_admin_dashboard(league_status, season_week, is_admin, nonce)

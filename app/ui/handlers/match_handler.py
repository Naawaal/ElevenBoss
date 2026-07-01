# app/ui/handlers/match_handler.py

import logging
import discord
import uuid
from app.ui.handlers.session import ui_session_manager
from app.services.match_service import MatchService
from app.ui.renderers.match_renderer import render_match_detail
from app.ui.components import V2View

logger = logging.getLogger("app.ui.handlers.match_handler")

async def handle_view_recent_match(
    guild_id: int,
    user: discord.Member,
    nonce: str | None = None
) -> V2View:
    """
    Orchestrates loading the recent match detail report.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
    else:
        session = ui_session_manager.create_session(user.id, guild_id)
        nonce = session.session_id
        
    result = await MatchService.get_recent_match(guild_id)
    if not result.success:
        raise ValueError(result.message)
        
    logger.info(f"match_recent_report_viewed: guild_id={guild_id}, user_id={user.id}")
    return render_match_detail(result, nonce)

async def handle_view_match_detail(
    guild_id: int,
    user: discord.Member,
    fixture_id: str | uuid.UUID,
    nonce: str | None = None
) -> V2View:
    """
    Orchestrates loading a specific match detail report by fixture ID.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
    else:
        session = ui_session_manager.create_session(user.id, guild_id)
        nonce = session.session_id
        
    result = await MatchService.get_match_detail(guild_id, fixture_id)
    if not result.success:
        raise ValueError(result.message)
        
    logger.info(f"match_detail_report_viewed: guild_id={guild_id}, user_id={user.id}, fixture_id={fixture_id}")
    return render_match_detail(result, nonce)

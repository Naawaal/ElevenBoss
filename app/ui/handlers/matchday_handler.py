# app/ui/handlers/matchday_handler.py

import logging
import discord
from app.ui.handlers.session import ui_session_manager
from app.ui.handlers.league_handler import check_admin_permission
from app.services.matchday_service import MatchdayService
from app.ui.renderers.matchday_renderer import render_matchday_status, render_matchday_run
from app.ui.components import V2View

logger = logging.getLogger("app.ui.handlers.matchday_handler")

async def handle_view_matchday_status(
    guild_id: int,
    user: discord.Member,
    nonce: str | None = None
) -> V2View:
    """
    Orchestrates loading the matchday status screen.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
    else:
        session = ui_session_manager.create_session(user.id, guild_id)
        nonce = session.session_id
        
    status_res = await MatchdayService.get_matchday_status(guild_id)
    if not status_res.success:
        raise ValueError(status_res.message)
        
    is_admin = await check_admin_permission(guild_id, user)
    logger.info(f"matchday_status_viewed: guild_id={guild_id}, user_id={user.id}")
    return render_matchday_status(status_res, nonce, is_admin)

async def handle_run_matchday(
    guild_id: int,
    user: discord.Member,
    nonce: str
) -> V2View:
    """
    Orchestrates simulating the current week's matchday.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)
        
    is_admin = await check_admin_permission(guild_id, user)
    if not is_admin:
        raise ValueError("Only server administrators or game admins can simulate the matchday.")
        
    run_res = await MatchdayService.run_current_matchday(
        guild_id=guild_id,
        discord_user_id=user.id,
        is_admin=is_admin
    )
    if not run_res.success:
        raise ValueError(run_res.message)
        
    logger.info(f"matchday_simulated: guild_id={guild_id}, week={run_res.simulated_week}")
    return render_matchday_run(run_res, nonce)

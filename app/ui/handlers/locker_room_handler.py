import logging
from app.services.club_service import get_manager_club_summary
from app.ui.handlers.session import ui_session_manager
from app.ui.renderers import render_locker_room, render_club_dashboard, render_help

logger = logging.getLogger("app.ui.handlers.locker_room_handler")

async def handle_open_locker_room(guild_id: int, discord_user_id: int, nonce: str | None = None):
    """
    Validates the manager/club and returns the Locker Room layout view.
    If nonce is provided, validates the session. If not, creates a new session.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
        if not valid:
            logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
            raise ValueError(err_msg)
            
    summary = await get_manager_club_summary(guild_id, discord_user_id)
    if not summary:
        logger.warning(f"ui_interaction_rejected: reason=unregistered_user, user_id={discord_user_id}")
        raise ValueError("You are not registered as a manager with a club. Run `/register` to get started.")
        
    if not nonce:
        session = ui_session_manager.create_session(discord_user_id, guild_id)
        nonce = session.session_id
        
    logger.info(f"ui_locker_opened: guild_id={guild_id}, discord_user_id={discord_user_id}, session_id={nonce}")
    return render_locker_room(summary, nonce)

async def handle_view_club_dashboard(guild_id: int, discord_user_id: int, nonce: str):
    """
    Validates session and returns the Club Dashboard layout.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    summary = await get_manager_club_summary(guild_id, discord_user_id)
    if not summary:
        raise ValueError("Manager or club not found. Please register first.")
        
    logger.info(f"ui_screen_rendered: screen=club_dashboard, guild_id={guild_id}, discord_user_id={discord_user_id}")
    return render_club_dashboard(summary, nonce)

async def handle_view_help(guild_id: int, discord_user_id: int, nonce: str):
    """
    Validates session and returns the Help layout.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    logger.info(f"ui_screen_rendered: screen=help, guild_id={guild_id}, discord_user_id={discord_user_id}")
    return render_help(nonce)

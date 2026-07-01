import logging
from app.services.club_service import get_manager_club_summary
from app.services.squad_service import get_squad
from app.ui.handlers.session import ui_session_manager
from app.ui.renderers import render_squad

logger = logging.getLogger("app.ui.handlers.squad_handler")

async def handle_view_squad(guild_id: int, discord_user_id: int, page: int, nonce: str | None = None):
    """
    Validates session/registration and renders the paginated squad layout.
    Saves the active page number to the session metadata.
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
        
    players = await get_squad(guild_id, discord_user_id)
    if players is None:
        raise ValueError("Could not load squad details.")
        
    if not nonce:
        session = ui_session_manager.create_session(discord_user_id, guild_id)
        nonce = session.session_id
    else:
        session = ui_session_manager.get_session(nonce)
        
    # Store page in session metadata for state persistence
    if session:
        session.metadata["squad_page"] = page
        
    logger.info(f"ui_squad_page_changed: page={page}, guild_id={guild_id}, discord_user_id={discord_user_id}")
    return render_squad(summary["club_name"], players, page, nonce)

import logging
from app.services.player_service import get_player_detail, search_player_by_name
from app.ui.handlers.session import ui_session_manager
from app.ui.renderers import render_player_detail, render_player_search, render_player_matches

logger = logging.getLogger("app.ui.handlers.player_handler")

async def handle_view_player_search(guild_id: int, discord_user_id: int, nonce: str):
    """
    Validates session and returns the player search instruction page layout.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
    return render_player_search(nonce)

async def handle_view_player_detail(guild_id: int, discord_user_id: int, player_id: str, nonce: str):
    """
    Validates session and returns the details layout for a specific player.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    player = await get_player_detail(guild_id, discord_user_id, player_id)
    if not player:
        logger.warning(f"ui_interaction_rejected: reason=player_not_found_or_unauthorized, player_id={player_id}, user_id={discord_user_id}")
        raise ValueError("Player not found or does not belong to your club.")
        
    logger.info(f"ui_player_detail_opened: player_id={player_id}, guild_id={guild_id}, discord_user_id={discord_user_id}")
    return render_player_detail(player, nonce)

async def handle_search_player_by_name(guild_id: int, discord_user_id: int, query: str, nonce: str | None = None):
    """
    Searches for players in the club. If exactly one player matches, shows their detail screen.
    If multiple players match, prompts the user with a select menu.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
        if not valid:
            logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
            raise ValueError(err_msg)
            
    matches = await search_player_by_name(guild_id, discord_user_id, query)
    if matches is None:
        logger.warning(f"ui_interaction_rejected: reason=unregistered_user, user_id={discord_user_id}")
        raise ValueError("You are not registered as a manager with a club. Run `/register` to get started.")
        
    if not matches:
        logger.info(f"ui_interaction_rejected: reason=no_players_matched, query={query}, user_id={discord_user_id}")
        raise ValueError(f"No players found matching '{query}'.")
        
    if not nonce:
        session = ui_session_manager.create_session(discord_user_id, guild_id)
        nonce = session.session_id
        
    if len(matches) == 1:
        logger.info(f"ui_player_detail_opened: player_id={matches[0]['id']}, guild_id={guild_id}, discord_user_id={discord_user_id}")
        return render_player_detail(matches[0], nonce)
        
    logger.info(f"ui_screen_rendered: screen=player_match_select, query={query}, matches={len(matches)}, guild_id={guild_id}, discord_user_id={discord_user_id}")
    return render_player_matches(query, matches, nonce)

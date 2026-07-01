# app/ui/handlers/lineup_handler.py

import logging
import io
import discord
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, get_players_by_club_id
from app.services.lineup_service import LineupService
from app.ui.handlers.session import ui_session_manager
from app.ui.renderers.lineup_renderer import render_lineup_screen

logger = logging.getLogger("app.ui.handlers.lineup_handler")

async def _resolve_and_render(guild_id: int, discord_user_id: int, session, nonce: str):
    """
    Helper to resolve player IDs in session metadata into Player models and render the lineup screen.
    """
    formation = session.metadata.get("formation", "4-4-2")
    starters_map = session.metadata.get("starters", {})
    bench_list = session.metadata.get("bench", [])
    warnings = session.metadata.get("warnings", [])
    is_dirty = session.metadata.get("is_dirty", False)
    club_name = session.metadata.get("club_name", "My Club")
    manager_name = session.metadata.get("manager_name", "Manager")
    
    # Fetch active players of the club
    async with get_session() as db_session:
        manager = await get_manager_by_discord_id(db_session, guild_id, discord_user_id)
        if not manager or not manager.club_id:
            raise ValueError("You are not registered as a manager with a club. Run `/register` to get started.")
        club_players = await get_players_by_club_id(db_session, manager.club_id)
        
    player_map = {str(p.id): p for p in club_players}
    
    # Resolve starters and bench
    resolved_starters = {}
    for slot, pid in starters_map.items():
        if pid in player_map:
            resolved_starters[slot] = player_map[pid]
            
    resolved_bench = []
    for pid in bench_list:
        if pid in player_map:
            resolved_bench.append(player_map[pid])
            
    # Generate the tactical board image
    img_bytes = LineupService.generate_board_image(
        club_name=club_name,
        manager_name=manager_name,
        formation=formation,
        starters=resolved_starters,
        bench=resolved_bench,
        warnings=warnings,
        is_dirty=is_dirty
    )
    
    file = None
    has_image = False
    if img_bytes:
        file = discord.File(fp=io.BytesIO(img_bytes), filename="lineup.png")
        has_image = True
        
    view = render_lineup_screen(
        club_name=club_name,
        formation=formation,
        starters=resolved_starters,
        bench=resolved_bench,
        warnings=warnings,
        is_dirty=is_dirty,
        nonce=nonce,
        has_image=has_image
    )
    
    return view, file

async def handle_open_lineup_screen(guild_id: int, discord_user_id: int, nonce: str | None = None, manager_name: str = "Manager"):
    """
    Initializes or opens the lineup management screen.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
        if not valid:
            logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
            raise ValueError(err_msg)
        session = ui_session_manager.get_session(nonce)
    else:
        session = ui_session_manager.create_session(discord_user_id, guild_id)
        nonce = session.session_id
        session.metadata["manager_name"] = manager_name
        
    res = await LineupService.get_lineup_screen_data(guild_id, discord_user_id)
    if not res.success:
        if res.code == "NO_CLUB":
            logger.warning(f"ui_interaction_rejected: reason=unregistered_user, user_id={discord_user_id}")
        else:
            logger.error(f"ui_error: failed to load lineup data: {res.message}")
        raise ValueError(res.message)
        
    # Cache in session metadata
    session.metadata["formation"] = res.formation
    session.metadata["starters"] = {slot: str(p.id) for slot, p in res.starters.items()}
    session.metadata["bench"] = [str(p.id) for p in res.bench]
    session.metadata["warnings"] = res.warnings
    session.metadata["is_dirty"] = False
    session.metadata["club_name"] = res.club_name
    
    return await _resolve_and_render(guild_id, discord_user_id, session, nonce)

async def handle_select_formation(guild_id: int, discord_user_id: int, formation: str, nonce: str):
    """
    Updates the selected formation and generates a preview lineup.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    session = ui_session_manager.get_session(nonce)
    
    # Generate auto lineup preview for the new formation immediately
    res = await LineupService.preview_auto_lineup(guild_id, discord_user_id, formation)
    if not res.success:
        raise ValueError(res.message)
        
    session.metadata["formation"] = formation
    session.metadata["starters"] = {slot: str(p.id) for slot, p in res.starters.items()}
    session.metadata["bench"] = [str(p.id) for p in res.bench]
    session.metadata["warnings"] = res.warnings
    session.metadata["is_dirty"] = True
    
    logger.info(
        "lineup_formation_selected: guild_id=%s, discord_user_id=%s, formation=%s",
        str(guild_id), str(discord_user_id), formation
    )
    
    return await _resolve_and_render(guild_id, discord_user_id, session, nonce)

async def handle_auto_lineup(guild_id: int, discord_user_id: int, nonce: str):
    """
    Generates a preview lineup using the currently selected formation.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    session = ui_session_manager.get_session(nonce)
    formation = session.metadata.get("formation", "4-4-2")
    
    res = await LineupService.preview_auto_lineup(guild_id, discord_user_id, formation)
    if not res.success:
        raise ValueError(res.message)
        
    session.metadata["starters"] = {slot: str(p.id) for slot, p in res.starters.items()}
    session.metadata["bench"] = [str(p.id) for p in res.bench]
    session.metadata["warnings"] = res.warnings
    session.metadata["is_dirty"] = True
    
    return await _resolve_and_render(guild_id, discord_user_id, session, nonce)

async def handle_save_lineup(guild_id: int, discord_user_id: int, nonce: str):
    """
    Saves the temporary preview lineup into the database.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    session = ui_session_manager.get_session(nonce)
    formation = session.metadata.get("formation", "4-4-2")
    starters = session.metadata.get("starters", {})
    bench = session.metadata.get("bench", [])
    
    if len(starters) < 11:
        raise ValueError("Cannot save an incomplete lineup. Please fill all slots.")
        
    res = await LineupService.save_lineup(guild_id, discord_user_id, formation, starters, bench)
    if not res.success:
        raise ValueError(res.message)
        
    session.metadata["is_dirty"] = False
    
    # We keep the warnings in rendering to show any tactical warnings of the saved lineup
    return await _resolve_and_render(guild_id, discord_user_id, session, nonce)

async def handle_refresh_lineup(guild_id: int, discord_user_id: int, nonce: str):
    """
    Refreshes the lineup screen from database state, discarding unsaved changes.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.warning(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)
        
    session = ui_session_manager.get_session(nonce)
    
    res = await LineupService.get_lineup_screen_data(guild_id, discord_user_id)
    if not res.success:
        raise ValueError(res.message)
        
    session.metadata["formation"] = res.formation
    session.metadata["starters"] = {slot: str(p.id) for slot, p in res.starters.items()}
    session.metadata["bench"] = [str(p.id) for p in res.bench]
    session.metadata["warnings"] = res.warnings
    session.metadata["is_dirty"] = False
    session.metadata["club_name"] = res.club_name
    
    return await _resolve_and_render(guild_id, discord_user_id, session, nonce)

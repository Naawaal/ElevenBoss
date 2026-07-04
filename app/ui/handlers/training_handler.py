# app/ui/handlers/training_handler.py

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.db.session import get_session
from app.services.training_service import TrainingService
from app.ui.handlers.session import ui_session_manager
from app.models.club import Club
from app.models.player import Player
from app.models.season import Season
from app.ui.layouts.training import (
    build_training_dashboard_layout,
    build_training_intensity_layout,
    build_training_default_plan_layout,
    build_player_plans_layout,
    build_set_player_plan_layout,
    build_training_condition_layout,
    build_training_outlook_layout,
)

logger = logging.getLogger("app.ui.handlers.training_handler")


async def _get_context(session: AsyncSession, guild_id: int, discord_user_id: int):
    """Helper to retrieve manager, club, league, and active season."""
    from app.repositories import (
        get_manager_by_discord_id,
        get_club_by_manager_id,
        get_active_or_draft_league_by_guild,
        get_active_season_for_league,
    )
    manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
    if not manager or not manager.club_id:
        raise ValueError("Manager or club not found. Please register first.")

    club = await get_club_by_manager_id(session, guild_id, manager.id)
    if not club:
        raise ValueError("Club not found.")

    league = await get_active_or_draft_league_by_guild(session, str(guild_id))
    if not league:
        raise ValueError("No active league found for this guild.")

    active_season = await get_active_season_for_league(session, guild_id, league.id)
    if not active_season:
        raise ValueError("No active season found for this league.")

    return club, active_season


async def handle_open_training_dashboard(
    guild_id: int, discord_user_id: int, nonce: str, success_msg: str | None = None
):
    """
    Validates session and opens the main Training Dashboard view.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.info(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        overview = await TrainingService.get_club_training_overview(
            session, str(guild_id), club.id, season.id
        )
        return build_training_dashboard_layout(overview, nonce, success_msg=success_msg)


async def handle_open_intensity_screen(guild_id: int, discord_user_id: int, nonce: str):
    """
    Validates session and opens the training intensity config screen.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        from app.repositories.training_repository import get_or_create_training_settings
        settings = await get_or_create_training_settings(session, club.id, season.id, str(guild_id))
        return build_training_intensity_layout(settings.intensity, nonce)


async def handle_set_intensity(guild_id: int, discord_user_id: int, intensity: str, nonce: str):
    """
    Sets the club training intensity and returns to the training overview dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        await TrainingService.set_club_intensity(session, club.id, season.id, str(guild_id), intensity)
        await session.commit()

    return await handle_open_training_dashboard(
        guild_id, discord_user_id, nonce, success_msg=f"Training intensity set to **{intensity.title()}**!"
    )


async def handle_open_default_plan_screen(guild_id: int, discord_user_id: int, nonce: str):
    """
    Validates session and opens the default plan config screen.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        from app.repositories.training_repository import get_or_create_training_settings
        settings = await get_or_create_training_settings(session, club.id, season.id, str(guild_id))
        return build_training_default_plan_layout(settings.default_plan, nonce)


async def handle_set_default_plan(guild_id: int, discord_user_id: int, plan: str, nonce: str):
    """
    Sets the club default training plan and returns to the training overview dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        await TrainingService.set_club_default_plan(session, club.id, season.id, str(guild_id), plan)
        await session.commit()

    return await handle_open_training_dashboard(
        guild_id, discord_user_id, nonce, success_msg=f"Default plan set to **{plan.title()}**!"
    )


async def handle_open_player_plans(guild_id: int, discord_user_id: int, nonce: str, page: int = 1):
    """
    Opens the paginated player plans list screen.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        
        # Save page index in session metadata
        ui_session = ui_session_manager.get_session(nonce)
        if ui_session:
            ui_session.metadata["training_plans_page"] = page

        # Load players (non-retired, sorted by OVR desc)
        players_stmt = select(Player).where(
            and_(
                Player.club_id == club.id,
                Player.is_retired == False
            )
        ).order_by(Player.overall.desc())
        players_res = await session.execute(players_stmt)
        players = list(players_res.scalars().all())

        # Load dev states
        from app.repositories.training_repository import get_dev_state_map_for_players, get_or_create_training_settings
        dev_states = await get_dev_state_map_for_players(session, [p.id for p in players], season.id)
        settings = await get_or_create_training_settings(session, club.id, season.id, str(guild_id))

        return build_player_plans_layout(players, dev_states, settings.default_plan, nonce, page)


async def handle_open_set_player_plan(guild_id: int, discord_user_id: int, player_id_str: str, nonce: str):
    """
    Opens the set plan screen for an individual player.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    try:
        player_id = uuid.UUID(player_id_str)
    except ValueError:
        raise ValueError("Invalid player ID format.")

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        
        from app.repositories import get_player_by_id
        player = await get_player_by_id(session, player_id)
        if not player or player.club_id != club.id:
            raise ValueError("Player not found in your club.")

        from app.repositories.training_repository import get_or_create_dev_state, get_or_create_training_settings
        dev_state = await get_or_create_dev_state(session, player.id, season.id, club.id, str(guild_id))
        settings = await get_or_create_training_settings(session, club.id, season.id, str(guild_id))
        
        current_plan = dev_state.plan_type if dev_state.plan_type else settings.default_plan
        return build_set_player_plan_layout(player, current_plan, nonce)


async def handle_set_player_plan(guild_id: int, discord_user_id: int, player_id_str: str, plan: str, nonce: str):
    """
    Sets the individual player's training plan and returns to the player plans list view.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    try:
        player_id = uuid.UUID(player_id_str)
    except ValueError:
        raise ValueError("Invalid player ID format.")

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        
        from app.repositories import get_player_by_id
        player = await get_player_by_id(session, player_id)
        if not player or player.club_id != club.id:
            raise ValueError("Player not found in your club.")

        await TrainingService.set_player_training_plan(
            session, club.id, player.id, season.id, str(guild_id), plan
        )
        await session.commit()

    # Get cached page from session metadata
    ui_session = ui_session_manager.get_session(nonce)
    page = ui_session.metadata.get("training_plans_page", 1) if ui_session else 1

    return await handle_open_player_plans(guild_id, discord_user_id, nonce, page)


async def handle_open_condition_report(guild_id: int, discord_user_id: int, nonce: str, page: int = 1):
    """
    Opens the paginated condition report screen.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)

        # Load players
        players_stmt = select(Player).where(
            and_(
                Player.club_id == club.id,
                Player.is_retired == False
            )
        ).order_by(Player.overall.desc())
        players_res = await session.execute(players_stmt)
        players = list(players_res.scalars().all())

        # Load dev states
        from app.repositories.training_repository import get_dev_state_map_for_players
        dev_states = await get_dev_state_map_for_players(session, [p.id for p in players], season.id)

        return build_training_condition_layout(players, dev_states, nonce, page)


async def handle_open_development_outlook(guild_id: int, discord_user_id: int, nonce: str, page: int = 1):
    """
    Opens the paginated development outlook screen.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        club, season = await _get_context(session, guild_id, discord_user_id)
        overview = await TrainingService.get_club_training_overview(
            session, str(guild_id), club.id, season.id
        )
        return build_training_outlook_layout(overview.development_outlook, nonce, page)

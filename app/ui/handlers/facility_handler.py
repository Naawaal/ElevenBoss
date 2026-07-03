# app/ui/handlers/facility_handler.py

import logging
from app.db.session import get_session
from app.services.club_service import get_manager_club_summary
from app.services.facility_service import FacilityService
from app.ui.handlers.session import ui_session_manager
from app.ui.layouts.facility_upgrade import build_facility_upgrade_layout
from app.models.facility import FacilityType

logger = logging.getLogger("app.ui.handlers.facility_handler")

async def handle_view_upgrade_center(guild_id: int, discord_user_id: int, nonce: str, success_message: str | None = None):
    """
    Validates session and returns the Facility Upgrade layout view.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.info(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)

    # Use get_manager_club_summary to get the latest club data with facilities
    summary = await get_manager_club_summary(guild_id, discord_user_id)
    if not summary:
        raise ValueError("Manager or club not found. Please register first.")

    return build_facility_upgrade_layout(summary, nonce, success_message=success_message)

async def handle_upgrade_facility(guild_id: int, discord_user_id: int, facility_type: FacilityType, nonce: str):
    """
    Validates session, executes the facility upgrade, and returns the updated Facility Upgrade layout.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, discord_user_id)
    if not valid:
        logger.info(f"ui_interaction_rejected: reason=session_validation_failed, user_id={discord_user_id}, nonce={nonce}")
        raise ValueError(err_msg)

    success_msg = None
    # Execute upgrade inside a single database transaction context
    async with get_session() as session:
        from app.repositories import get_manager_by_discord_id
        manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
        if not manager or not manager.club_id:
            raise ValueError("Manager or club not found. Please register first.")

        try:
            facility = await FacilityService.start_upgrade(session, manager.club_id, facility_type)
            await session.commit()
            success_msg = f"Upgrade started for {facility_type.value.replace('_', ' ').title()} to Level {facility.level + 1}!"
        except ValueError as ve:
            await session.rollback()
            raise ve
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to start facility upgrade: {e}", exc_info=e)
            raise e

    # Render the updated upgrade center page
    return await handle_view_upgrade_center(guild_id, discord_user_id, nonce, success_message=success_msg)

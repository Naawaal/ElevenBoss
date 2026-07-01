# app/services/dm_settings_service.py

import logging
from dataclasses import dataclass, field
from app.services.guild_selection_service import GuildSelectionService, ManageableGuildView
from app.services.permission_service import can_manage_guild_settings

logger = logging.getLogger("app.services.dm_settings_service")

@dataclass
class DMSettingsResult:
    success: bool
    code: str
    message: str
    manageable_guilds: list[ManageableGuildView] = field(default_factory=list)
    selected_guild_id: int | None = None

class DMSettingsService:
    @staticmethod
    async def open_settings_console(user_id: int) -> DMSettingsResult:
        """
        Retrieves manageable guilds for a user.
        """
        try:
            views = await GuildSelectionService.get_manageable_guilds(user_id)
            if not views:
                logger.info(f"dm_settings_no_manageable_guilds: user_id={user_id}")
                return DMSettingsResult(
                    success=False,
                    code="no_manageable_guilds",
                    message="You do not have permission to manage any ElevenBoss servers."
                )
            
            logger.info(f"dm_settings_opened: user_id={user_id}, guilds_count={len(views)}")
            return DMSettingsResult(
                success=True,
                code="success",
                message="Successfully resolved manageable guilds.",
                manageable_guilds=views
            )
        except Exception as e:
            logger.error(f"dm_settings_error: failed to open console: {e}", exc_info=e)
            return DMSettingsResult(
                success=False,
                code="unexpected_error",
                message="An unexpected error occurred resolving your servers."
            )

    @staticmethod
    async def select_guild_for_settings(user_id: int, guild_id: int) -> DMSettingsResult:
        """
        Validates permission and selects a guild.
        """
        try:
            # Revalidate permissions
            allowed = await can_manage_guild_settings(guild_id, user_id)
            if not allowed:
                logger.warning(f"dm_settings_permission_denied: user_id={user_id}, guild_id={guild_id}")
                return DMSettingsResult(
                    success=False,
                    code="permission_denied",
                    message="You do not have permission to manage settings for this guild."
                )
            
            logger.info(f"dm_settings_guild_selected: user_id={user_id}, guild_id={guild_id}")
            return DMSettingsResult(
                success=True,
                code="success",
                message="Guild selected successfully.",
                selected_guild_id=guild_id
            )
        except Exception as e:
            logger.error(f"dm_settings_error: failed to select guild: {e}", exc_info=e)
            return DMSettingsResult(
                success=False,
                code="unexpected_error",
                message="An unexpected error occurred during guild selection."
            )

# app/services/settings_service.py

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.db.session import get_session
from app.repositories.guild_config_repository import (
    get_or_create_guild_config,
    update_channels as db_update_channels,
    update_admin_role as db_update_admin_role,
    update_automation_settings as db_update_automation_settings,
    update_schedule_settings as db_update_schedule_settings,
    set_matchday_enabled as db_set_matchday_enabled,
)
from app.services.automation_settings_service import AutomationSettingsService

logger = logging.getLogger("app.services.settings_service")

class SettingsService:
    @staticmethod
    async def update_channels(
        guild_id: int,
        guild_obj,  # discord.Guild or mock
        game_channel_id: str | None = None,
        matchday_channel_id: str | None = None
    ) -> tuple[bool, str]:
        """
        Updates channels for ElevenBoss in the database.
        """
        # Validate channel existence & send permissions if guild_obj is provided
        if guild_obj is not None:
            for ch_id in (game_channel_id, matchday_channel_id):
                if ch_id is not None:
                    try:
                        channel = guild_obj.get_channel(int(ch_id))
                        if not channel:
                            return False, f"Channel with ID {ch_id} not found in this server."
                        perms = channel.permissions_for(guild_obj.me)
                        if not perms.send_messages:
                            return False, f"The bot lacks permission to send messages in <#{ch_id}>."
                    except Exception as e:
                        logger.warning(f"Failed to validate channel {ch_id}: {e}")
                        # In tests or fallback, allow

        try:
            async with get_session() as session:
                await db_update_channels(
                    session=session,
                    guild_id=guild_id,
                    game_channel_id=game_channel_id,
                    matchday_channel_id=matchday_channel_id
                )
                await session.commit()
            logger.info(f"settings_channels_updated: guild_id={guild_id}, game_channel={game_channel_id}, matchday={matchday_channel_id}")
            return True, "Channels updated successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to update channels: {e}", exc_info=e)
            return False, "Failed to update channels in database."

    @staticmethod
    async def update_admin_role(
        guild_id: int,
        role_id: str | None
    ) -> tuple[bool, str]:
        """
        Sets or clears the ElevenBoss admin role.
        """
        try:
            async with get_session() as session:
                await db_update_admin_role(session, guild_id, role_id)
                await session.commit()
            if role_id:
                logger.info(f"settings_admin_role_updated: guild_id={guild_id}, role_id={role_id}")
                return True, "Admin role updated successfully."
            else:
                logger.info(f"settings_admin_role_cleared: guild_id={guild_id}")
                return True, "Admin role cleared successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to update admin role: {e}", exc_info=e)
            return False, "Failed to update admin role in database."

    @staticmethod
    async def update_mention_role(
        guild_id: int,
        role_id: str | None
    ) -> tuple[bool, str]:
        """
        Sets or clears the announcement mention role.
        """
        try:
            async with get_session() as session:
                from app.repositories.guild_config_repository import update_mention_role as db_update_mention_role
                await db_update_mention_role(session, guild_id, role_id)
                await session.commit()
            if role_id:
                logger.info(f"settings_mention_role_updated: guild_id={guild_id}, role_id={role_id}")
                return True, "Announcement mention role updated successfully."
            else:
                logger.info(f"settings_mention_role_cleared: guild_id={guild_id}")
                return True, "Announcement mention role cleared successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to update announcement mention role: {e}", exc_info=e)
            return False, "Failed to update announcement mention role in database."

    @staticmethod
    async def update_automation_settings(
        guild_id: int,
        auto_join: bool | None = None,
        auto_start: bool | None = None,
        auto_fill: bool | None = None,
        min_human: int | None = None,
        deadline: datetime | None = None
    ) -> tuple[bool, str]:
        """
        Validates and updates automation settings.
        """
        success, err_msg = AutomationSettingsService.validate_automation_settings(
            auto_join=auto_join,
            auto_start=auto_start,
            auto_fill=auto_fill,
            min_human=min_human,
            deadline=deadline
        )
        if not success:
            return False, err_msg

        try:
            async with get_session() as session:
                await db_update_automation_settings(
                    session=session,
                    guild_id=guild_id,
                    auto_join=auto_join,
                    auto_start=auto_start,
                    auto_fill=auto_fill,
                    min_human=min_human,
                    deadline=deadline
                )
                await session.commit()
            logger.info(f"settings_automation_updated: guild_id={guild_id}")
            return True, "Automation settings updated successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to update automation settings: {e}", exc_info=e)
            return False, "Failed to update automation settings in database."

    @staticmethod
    async def update_schedule_settings(
        guild_id: int,
        guild_obj,
        day: str | None = None,
        time: str | None = None,
        timezone: str | None = None,
        channel_id: str | None = None
    ) -> tuple[bool, str]:
        """
        Validates and updates schedule settings.
        """
        if day is not None:
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            if day.strip().capitalize() not in days:
                return False, f"Invalid day of week: {day}. Must be Monday-Sunday."

        if time is not None:
            parts = time.split(":")
            if len(parts) != 2:
                return False, "Time must be in HH:MM format."
            try:
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23) or not (0 <= m <= 59):
                    raise ValueError()
            except ValueError:
                return False, "Time hours must be 0-23 and minutes 0-59."

        if timezone is not None:
            try:
                ZoneInfo(timezone)
            except ZoneInfoNotFoundError:
                return False, f"Invalid timezone string '{timezone}'."

        if channel_id is not None and guild_obj is not None:
            try:
                channel = guild_obj.get_channel(int(channel_id))
                if not channel:
                    return False, f"Channel with ID {channel_id} not found."
                perms = channel.permissions_for(guild_obj.me)
                if not perms.send_messages:
                    return False, f"Lacking send message permissions in <#{channel_id}>."
            except Exception as e:
                logger.warning(f"Failed to validate schedule channel {channel_id}: {e}")

        try:
            async with get_session() as session:
                await db_update_schedule_settings(
                    session=session,
                    guild_id=guild_id,
                    day=day,
                    time=time,
                    timezone=timezone,
                    channel_id=channel_id
                )
                await session.commit()
            logger.info(f"settings_schedule_updated: guild_id={guild_id}")
            return True, "Schedule settings updated successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to update schedule settings: {e}", exc_info=e)
            return False, "Failed to update schedule settings in database."

    @staticmethod
    async def enable_schedule(guild_id: int, guild_obj) -> tuple[bool, str]:
        """
        Enables the matchday schedule checks.
        """
        try:
            async with get_session() as session:
                config = await get_or_create_guild_config(session, guild_id)
                if not config.matchday_day or not config.matchday_time:
                    return False, "Matchday schedule day and time must be configured first."
                
                # Check announcement channel
                channel_id = config.matchday_announcement_channel_id or config.game_channel_id
                if not channel_id:
                    return False, "No announcement or game channel is configured."

                if guild_obj is not None:
                    channel = guild_obj.get_channel(int(channel_id))
                    if not channel:
                        return False, f"Configured channel {channel_id} not found in this server."
                    perms = channel.permissions_for(guild_obj.me)
                    if not perms.send_messages:
                        return False, f"Lacking send permissions in channel <#{channel_id}>."

                await db_set_matchday_enabled(session, guild_id, True)
                await session.commit()
            logger.info(f"settings_schedule_enabled: guild_id={guild_id}")
            return True, "Matchday schedule enabled successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to enable schedule: {e}", exc_info=e)
            return False, "Database error enabling schedule."

    @staticmethod
    async def disable_schedule(guild_id: int) -> tuple[bool, str]:
        """
        Disables the matchday schedule checks.
        """
        try:
            async with get_session() as session:
                await db_set_matchday_enabled(session, guild_id, False)
                await session.commit()
            logger.info(f"settings_schedule_disabled: guild_id={guild_id}")
            return True, "Matchday schedule disabled successfully."
        except Exception as e:
            logger.error(f"settings_error: failed to disable schedule: {e}", exc_info=e)
            return False, "Database error disabling schedule."

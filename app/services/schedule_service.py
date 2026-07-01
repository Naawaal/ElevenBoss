# app/services/schedule_service.py

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.models.guild_config import GuildConfig

logger = logging.getLogger("app.services.schedule_service")

class ScheduleService:
    @staticmethod
    def is_matchday_due(config: GuildConfig, now_utc: datetime) -> bool:
        """
        Determine if the scheduled matchday is currently due.
        Tolerance window: within 15 minutes after the scheduled local time.
        """
        if not config.matchday_enabled:
            return False
        if not config.matchday_day or not config.matchday_time:
            return False

        try:
            guild_tz = ZoneInfo(config.matchday_timezone)
            local_now = now_utc.astimezone(guild_tz)

            # Check day of the week (e.g. "Sunday")
            day_str = config.matchday_day.strip().capitalize()
            current_day_str = local_now.strftime("%A")
            if current_day_str != day_str:
                return False

            # Check time (HH:MM)
            time_parts = config.matchday_time.split(":")
            if len(time_parts) != 2:
                return False

            hour = int(time_parts[0])
            minute = int(time_parts[1])

            # Local scheduled time for today
            scheduled_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Difference in seconds between local now and scheduled local time
            diff = (local_now - scheduled_local).total_seconds()

            # Due if now is between the scheduled time and 15 minutes (900 seconds) past it
            if 0 <= diff <= 900:
                return True
        except Exception as e:
            logger.error(f"Error checking is_matchday_due for guild={config.guild_id}: {e}", exc_info=e)

        return False

    @staticmethod
    def get_last_scheduled_occurrence(config: GuildConfig, now_utc: datetime) -> datetime | None:
        """
        Calculates the most recent scheduled matchday datetime in UTC (occurring on or before now_utc).
        """
        if not config.matchday_enabled or not config.matchday_day or not config.matchday_time:
            return None

        try:
            guild_tz = ZoneInfo(config.matchday_timezone)
            local_now = now_utc.astimezone(guild_tz)

            time_parts = config.matchday_time.split(":")
            if len(time_parts) != 2:
                return None

            hour = int(time_parts[0])
            minute = int(time_parts[1])

            days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            target_day_idx = days_of_week.index(config.matchday_day.strip().capitalize())

            # Look back up to 7 days
            for d in range(8):
                test_date = local_now - timedelta(days=d)
                if test_date.weekday() == target_day_idx:
                    scheduled_local = test_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if scheduled_local <= local_now:
                        return scheduled_local.astimezone(ZoneInfo("UTC"))
        except Exception as e:
            logger.error(f"Error calculating last scheduled occurrence for guild={config.guild_id}: {e}", exc_info=e)

        return None

# app/services/automation_settings_service.py

import logging
from datetime import datetime

logger = logging.getLogger("app.services.automation_settings_service")

class AutomationSettingsService:
    @staticmethod
    def validate_automation_settings(
        auto_join: bool | None,
        auto_start: bool | None,
        auto_fill: bool | None,
        min_human: int | None,
        deadline: datetime | None
    ) -> tuple[bool, str]:
        """
        Validates the inputs for automation settings.
        Returns (success, error_message).
        """
        if min_human is not None:
            if min_human < 1:
                return False, "Minimum human clubs must be at least 1."
            if min_human > 16:
                return False, "Minimum human clubs cannot exceed the maximum supported league size (16)."

        if deadline is not None:
            if deadline <= datetime.utcnow():
                return False, "Registration deadline must be in the future."

        # If auto start is enabled, validate configuration logic
        # e.g., if auto_start_league is True, it requires either auto_fill_with_bot_clubs to be True,
        # or the league can start only when it becomes completely full naturally.
        return True, ""

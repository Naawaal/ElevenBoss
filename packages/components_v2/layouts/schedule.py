# app/ui/layouts/schedule.py

from datetime import datetime
from app.ui.components import (
    container,
    text_display,
    action_row,
    primary_button,
    secondary_button,
    V2View,
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button
from app.services.schedule_service import ScheduleService

def build_schedule_layout(config, is_admin: bool, nonce: str) -> V2View:
    """
    Builds the schedule details display using Components V2.
    """
    status_label = "🟢 SCHEDULE ACTIVE" if config.matchday_enabled else "🔴 SCHEDULE INACTIVE"
    
    # Calculate next scheduled run
    next_run_str = "N/A"
    warning_str = ""
    now_utc = datetime.utcnow()
    
    if config.matchday_enabled and config.matchday_day and config.matchday_time:
        last_occ = ScheduleService.get_last_scheduled_occurrence(config, now_utc)
        if last_occ:
            # If the last occurrence was in the past and no run was executed after it, flag as warning
            last_run = config.last_automation_run_at
            # Check if last run was before the last occurrence (allowing a tiny buffer)
            is_missed = False
            if not last_run or last_run < last_occ:
                # We missed it!
                is_missed = True
                
            if is_missed:
                warning_str = "\n⚠️ **WARNING:** The scheduled run time has passed, but it was not simulated. The bot might have been offline during the scheduled window. You can trigger a run manually using `/schedule run-now`."
            
            # Next occurrence is roughly last + 7 days
            from datetime import timedelta
            next_occ = last_occ + timedelta(days=7)
            next_run_str = f"{next_occ.strftime('%Y-%m-%d %H:%M')} UTC"
            
    text = (
        f"###📅 MATCHDAY AUTOMATION SCHEDULE\n"
        f"**Status:** `{status_label}`\n\n"
        f"🕒 **Scheduled Time:** `Every {config.matchday_day or 'None'} at {config.matchday_time or 'None'}`\n"
        f"🌍 **Timezone:** `{config.matchday_timezone}`\n"
        f"📢 **Channel:** <#{config.matchday_announcement_channel_id or config.game_channel_id or 'None'}>\n"
        f"⏭️ **Next Scheduled Run:** `{next_run_str}`\n"
        f"{warning_str}"
    )

    toggle_sched_id = encode_custom_id("schedule", "toggle", "main", nonce)
    run_now_id = encode_custom_id("schedule", "run_now", "main", nonce)
    refresh_id = encode_custom_id("schedule", "refresh", "main", nonce)

    rows = []
    
    if is_admin:
        toggle_label = "Disable Schedule" if config.matchday_enabled else "Enable Schedule"
        rows.append(action_row([
            primary_button(toggle_label, toggle_sched_id),
            primary_button("⚡ Run Now", run_now_id)
        ]))

    nav_buttons = [
        secondary_button("🔄 Refresh", refresh_id),
        close_button(nonce)
    ]
    rows.append(action_row(nav_buttons))

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)

    return V2View(comp_payload)

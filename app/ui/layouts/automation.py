# app/ui/layouts/automation.py

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

def build_automation_layout(
    config,
    league_status: str,
    season_week: str,
    next_run_str: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Builds the automation status display using Components V2.
    """
    status_text = f"**Status:** `{config.automation_status.upper()}`\n\n"
    
    last_run = "Never"
    if config.last_automation_run_at:
        last_run = config.last_automation_run_at.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
        
    last_res = config.last_automation_status or "None"
    
    # Check if there is an error
    error_warning = ""
    if config.last_automation_error:
        # Truncate safe/short display error
        err_msg = config.last_automation_error
        if len(err_msg) > 100:
            err_msg = err_msg[:97] + "..."
        error_warning = f"\n⚠️ **Last Error:** `{err_msg}`\n"

    text = (
        f"###🤖 ELEVENBOSS SYSTEM AUTOMATION STATUS\n"
        f"{status_text}"
        f"🏆 **League State:** `{league_status}`\n"
        f"⚽ **Season/Week:** `{season_week}`\n"
        f"📅 **Next Scheduled Matchday:** `{next_run_str}`\n\n"
        f"⏱️ **Last Run At:** `{last_run}`\n"
        f"🏁 **Last Result Code:** `{last_res}`\n"
        f"{error_warning}"
    )

    # Encode custom IDs
    run_check_id = encode_custom_id("automation", "run_check", "main", nonce)
    sched_settings_id = encode_custom_id("automation", "go_schedule", "main", nonce)
    league_status_id = encode_custom_id("automation", "go_league", "main", nonce)
    refresh_id = encode_custom_id("automation", "refresh", "main", nonce)

    rows = []
    
    # Row 1: Actions (Run Check & Schedule Settings are Admin-only)
    action_buttons = []
    if is_admin:
        action_buttons.append(primary_button("⚡ Run Check Now", run_check_id))
        action_buttons.append(secondary_button("⚙️ Schedule Settings", sched_settings_id))
    
    action_buttons.append(secondary_button("🏆 League Status", league_status_id))
    rows.append(action_row(action_buttons))

    # Row 2: Nav
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

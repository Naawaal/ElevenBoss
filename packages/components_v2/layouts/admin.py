# app/ui/layouts/admin.py

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

def build_admin_dashboard_layout(
    league_status: str,
    season_week: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Builds the Admin Recovery and Override Dashboard layout.
    """
    text = (
        f"###🛡️ ELEVENBOSS ADMIN RECOVERY & OVERRIDES\n\n"
        f"⚠️ **Caution:** These are manual override commands. Use them only when scheduling fails, "
        f"for developer testing, or during league bootstrapping emergency recovery.\n\n"
        f"🏆 **League Status:** `{league_status}`\n"
        f"📅 **Season / Week:** `{season_week}`\n"
    )

    # Encode custom IDs
    sim_matchday_id = encode_custom_id("admin", "matchday_run", "main", nonce)
    run_check_id = encode_custom_id("admin", "automation_check", "main", nonce)
    refresh_id = encode_custom_id("admin", "refresh", "main", nonce)

    rows = []
    
    if is_admin:
        rows.append(action_row([
            primary_button("⚡ Sim Matchday", sim_matchday_id),
            primary_button("🔍 Run Check", run_check_id)
        ]))

    rows.append(action_row([
        secondary_button("🔄 Refresh", refresh_id),
        close_button(nonce)
    ]))

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)

    return V2View(comp_payload)

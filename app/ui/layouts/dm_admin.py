# app/ui/layouts/dm_admin.py

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
    guild_name: str,
    league_status: str,
    season_week: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Builds the DM Admin Recovery and Override Dashboard layout.
    """
    text = (
        f"### 🛡️ ELEVENBOSS ADMIN OVERRIDES — {guild_name.upper()}\n\n"
        f"⚠️ **Caution:** These are manual override commands. Use them only when scheduling fails, "
        f"for developer testing, or during league bootstrapping emergency recovery.\n\n"
        f"🏆 **League Status:** `{league_status}`\n"
        f"📅 **Season / Week:** `{season_week}`\n"
    )

    sim_matchday_id = encode_custom_id("dm_admin", "matchday_run", "main", nonce)
    run_check_id = encode_custom_id("dm_admin", "automation_check", "main", nonce)
    league_start_id = encode_custom_id("dm_admin", "league_start", "main", nonce)
    switch_id = encode_custom_id("dm_settings", "switch", "guild", nonce)
    refresh_id = encode_custom_id("dm_admin", "view", "actions", nonce)

    rows = []
    
    if is_admin:
        rows.append(action_row([
            primary_button("⚡ Sim Matchday", sim_matchday_id),
            primary_button("🔍 Run Check", run_check_id),
            primary_button("🚀 Force Start", league_start_id)
        ]))

    rows.append(action_row([
        secondary_button("🔄 Switch Server", switch_id),
        secondary_button("🔄 Refresh", refresh_id),
        close_button(nonce)
    ]))

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

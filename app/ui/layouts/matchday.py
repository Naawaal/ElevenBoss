# app/ui/layouts/matchday.py

from app.ui.components import (
    container,
    text_display,
    action_row,
    primary_button,
    secondary_button,
    success_button,
    danger_button,
    V2View,
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button

def build_matchday_status_layout(data, nonce: str, is_admin: bool) -> V2View:
    """
    Builds the matchweek status screen payload.
    """
    emoji = "🏆"
    if data.status_label == "Season Complete":
        emoji = "🏁"
    elif data.status_label == "Already Played":
        emoji = "✅"
        
    text = (
        f"### {emoji} MATCHDAY CONTROL CENTER\n"
        f"**League:** {data.league_name}\n"
        f"**Season:** Season {data.season_number}\n"
        f"**Current Week:** Week {data.current_week}\n"
        f"\n"
        f"📊 **Week Summary**\n"
        f"📅 **Total Fixtures:** {data.total_fixtures}\n"
        f"🕐 **Scheduled:** {data.scheduled_fixtures}\n"
        f"✅ **Played:** {data.played_fixtures}\n"
        f"📈 **Status:** `{data.status_label.upper()}`\n"
    )
    
    if data.status_label == "Ready":
        text += "\n▶️ The current week is ready to simulate. Admin can run matchday."
    elif data.status_label == "Already Played":
        text += "\n✅ All matches for this week have been simulated. Advance to next week or review table."
    elif data.status_label == "Season Complete":
        text += "\n🏁 The season has concluded! Standings are final."
        
    # Custom IDs
    run_id = encode_custom_id("matchday", "run", "current", nonce)
    fixtures_id = encode_custom_id("fixtures", "view", "current", nonce)
    table_id = encode_custom_id("league", "view_table", "main", nonce)
    back_locker_id = encode_custom_id("nav", "back", "locker", nonce)
    
    rows = []
    
    # Admin Simulation Actions
    if is_admin:
        # Disable run button if already played or no fixtures/season complete
        can_run = data.status_label == "Ready"
        rows.append(action_row([
            success_button("⚡ Simulate Matchday", run_id, disabled=not can_run)
        ]))
        
    # Standard navigation actions
    nav_buttons = [
        primary_button("📊 View Table", table_id),
        success_button("📅 View Fixtures", fixtures_id),
        refresh_button("matchday", "refresh", nonce),
        secondary_button("🏠 Locker Room", back_locker_id),
        close_button(nonce)
    ]
    rows.append(action_row(nav_buttons))
    
    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    
    return V2View(comp_payload)

def build_matchday_run_layout(data, nonce: str) -> V2View:
    """
    Builds the matchday run success results screen payload.
    """
    summary = f"### ⚡ WEEK {data.simulated_week} SIMULATED\n"
    summary += f"**League:** {data.league_name} | **Season:** Season {data.season_number}\n\n"
    
    # List match results
    summary += "⚽ **Match Results**\n"
    for r in data.results:
        summary += f"• **{r.home_club_name}**  {r.home_goals}–{r.away_goals}  **{r.away_club_name}**\n"
        
    summary += "\n📈 League standings and stats have been updated."
    
    if data.season_completed:
        summary += "\n\n🏁 **Season Concluded!** This was the final week of the season."
    else:
        summary += f"\n\n➡️ The season has advanced to **Week {data.simulated_week + 1}**."
        
    # Custom IDs
    table_id = encode_custom_id("league", "view_table", "main", nonce)
    fixtures_id = encode_custom_id("fixtures", "view", "current", nonce)
    recent_id = encode_custom_id("match", "recent", "view", nonce)
    back_locker_id = encode_custom_id("nav", "back", "locker", nonce)
    
    buttons = [
        success_button("📊 View Table", table_id),
        primary_button("📅 View Fixtures", fixtures_id),
        primary_button("🎥 Recent Match Details", recent_id),
        secondary_button("🏠 Locker Room", back_locker_id),
        close_button(nonce)
    ]
    
    comp_payload = [
        container([text_display(summary)]),
        action_row(buttons)
    ]
    return V2View(comp_payload)

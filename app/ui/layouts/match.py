# app/ui/layouts/match.py

from app.ui.components import (
    container,
    text_display,
    action_row,
    primary_button,
    secondary_button,
    success_button,
    V2View,
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button

def build_match_detail_layout(data, nonce: str) -> V2View:
    """
    Builds the Components V2 match detail screen.
    """
    header = (
        f"### 🏟️ MATCH REPORT\n"
        f"**{data.home_club_name}**  {data.home_goals}–{data.away_goals}  **{data.away_club_name}**\n"
        f"🏅 **Man of the Match:** {data.motm_player_name}\n"
    )
    
    # ── Match Stats ──
    stats = (
        f"📊 **Match Stats**\n"
        f"• **Possession:** {data.home_possession}% vs {data.away_possession}%\n"
        f"• **Shots:** {data.home_shots} vs {data.away_shots}\n"
        f"• **Shots on Target:** {data.home_shots_on_target} vs {data.away_shots_on_target}\n"
    )
    
    # ── Timeline / Commentary ──
    timeline = "⏳ **Match Timeline**\n"
    if not data.timeline:
        timeline += "• No significant events occurred in this match."
    else:
        for event in data.timeline:
            minute = event["minute"]
            etype = event["type"]
            desc = event["description"]
            
            # Emoji prefix for timeline readability
            prefix = "⏱️"
            if etype == "match_start":
                prefix = "📢"
            elif etype == "half_time":
                prefix = "⏸️"
            elif etype == "full_time":
                prefix = "🏁"
            elif etype == "goal":
                prefix = "⚽"
            elif etype == "yellow_card":
                prefix = "🟨"
            elif etype == "red_card":
                prefix = "🟥"
            elif etype == "substitution":
                prefix = "🔄"
            elif etype == "injury":
                prefix = "🚑"
                
            timeline += f"• **{minute}'** {prefix} {desc}\n"
            
    # Navigation Custom IDs
    matchday_id = encode_custom_id("matchday", "status", "current", nonce)
    table_id = encode_custom_id("league", "view_table", "main", nonce)
    
    buttons = [
        success_button("🏟️ Matchday Center", matchday_id),
        primary_button("📊 View Table", table_id),
        close_button(nonce)
    ]
    
    comp_payload = [
        container([text_display(header)]),
        container([text_display(stats)]),
        container([text_display(timeline)]),
        action_row(buttons)
    ]
    return V2View(comp_payload)

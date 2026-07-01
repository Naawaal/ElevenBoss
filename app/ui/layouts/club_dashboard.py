from app.ui.components import container, text_display, action_row, primary_button, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button, back_button
from app.ui.formatters import format_money

def build_club_dashboard_layout(data: dict, nonce: str) -> V2View:
    """
    Builds the Club Dashboard layout.
    """
    budget_str = format_money(data["budget"])
    stadium_str = f"{data['stadium_capacity']:,} capacity"
    
    text = (
        f"### 📊 CLUB DASHBOARD — {data['club_name']}\n"
        f"👤 **Manager:** <@{data['discord_user_id']}>\n"
        f"💰 **Budget:** {budget_str}\n"
        f"👥 **Squad Size:** {data['squad_size']} players\n"
        f"📈 **Average Overall:** {data['average_overall']} OVR\n"
        f"⭐ **Best Player:** {data['best_player_name']} ({data['best_player_ovr']} OVR)\n"
        f"🔮 **Highest Potential Prospect:** {data['highest_pot_name']} (POT {data['highest_pot_val']})\n"
        f"🏟️ **Stadium:** {stadium_str}\n"
        f"🏆 **League Status:** {data['league_status']}"
    )
    
    squad_id = encode_custom_id("locker", "view", "squad", nonce)
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            primary_button("👥 View Squad", squad_id),
            refresh_button("locker", "club", nonce),
            back_button("locker", nonce),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

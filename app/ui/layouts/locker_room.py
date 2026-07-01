from app.ui.components import container, text_display, action_row, primary_button, secondary_button, success_button, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button
from app.ui.formatters import format_money

def build_locker_room_layout(data: dict, nonce: str) -> V2View:
    """
    Builds the Locker Room dashboard layout.
    """
    budget_str = format_money(data["budget"])
    
    text = (
        f"### 🏟️ LOCKER ROOM — {data['club_name']}\n"
        f"👤 **Manager:** <@{data['discord_user_id']}>\n"
        f"👥 **Squad Size:** {data['squad_size']} players\n"
        f"📈 **Average Overall:** {data['average_overall']} OVR\n"
        f"⭐ **Best Player:** {data['best_player_name']} ({data['best_player_ovr']} OVR)\n"
        f"💰 **Budget:** {budget_str}\n"
        f"🏆 **League Status:** {data['league_status']}\n\n"
        f"🧭 **Next Action:** {data['next_suggested_action']}"
    )
    
    # Custom IDs
    squad_id = encode_custom_id("locker", "view", "squad", nonce)
    players_id = encode_custom_id("player", "view", "search", nonce)
    dashboard_id = encode_custom_id("locker", "open", "club", nonce)
    help_id = encode_custom_id("locker", "view", "help", nonce)
    lineup_id = encode_custom_id("lineup", "open", "main", nonce)
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            primary_button("👥 Squad", squad_id),
            primary_button("📋 Lineup", lineup_id),
            primary_button("🏃 Players", players_id),
            success_button("📊 Dashboard", dashboard_id)
        ]),
        action_row([
            refresh_button("locker", "club", nonce),
            secondary_button("❓ Help", help_id),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

def build_help_layout(nonce: str) -> V2View:
    """
    Builds the FCM bot help layout.
    """
    text = (
        "### 📚 Football Club Manager Help\n"
        "Manage your club, squad, and players using Discord Slash Commands and Components V2.\n\n"
        "**Available Commands:**\n"
        "• `/club` — Opens your private Locker Room hub.\n"
        "• `/squad` — View your squad list (paginated).\n"
        "• `/player [name]` — Search for a player or view their details.\n\n"
        "**Navigation:**\n"
        "Use the buttons under the layouts to move between pages. Ephemeral screens expire after 15 minutes of inactivity."
    )
    
    back_id = encode_custom_id("nav", "back", "locker", nonce)
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            secondary_button("◀ Back", back_id),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

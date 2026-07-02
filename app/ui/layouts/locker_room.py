from app.ui.components import container, text_display, action_row, primary_button, secondary_button, success_button, media_gallery, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button
from app.ui.formatters import format_money

def build_locker_room_layout(data: dict, nonce: str, has_image: bool = False) -> V2View:
    """
    Builds the Locker Room dashboard layout.
    """
    budget_str = format_money(data["budget"])
    avg_ovr = data.get("average_overall", 0)
    filled_ovr = min(10, max(0, int(avg_ovr / 10)))
    ovr_bar = "▰" * filled_ovr + "▱" * (10 - filled_ovr)

    # Monospace status card lines (40 characters wide)
    line_1 = f" Team Overall: {avg_ovr} OVR  {ovr_bar}"
    line_2 = f" Squad Size: {data['squad_size']} Players"
    line_3 = f" Club Budget: {budget_str}"
    line_4 = f" Status: {data['league_status']}"

    card_line_1 = f"║{line_1:<40}║"
    card_line_2 = f"║{line_2:<40}║"
    card_line_3 = f"║{line_3:<40}║"
    card_line_4 = f"║{line_4:<40}║"

    text = (
        f"🏟️ **LOCKER ROOM HUB** • **{data['club_name'].upper()}**\n"
        f"👤 **Manager:** <@{data['discord_user_id']}>\n\n"
        f"```yaml\n"
        f"╔════════════════════════════════════════╗\n"
        f"║           MANAGER HUB STATUS           ║\n"
        f"╠════════════════════════════════════════╣\n"
        f"{card_line_1}\n"
        f"{card_line_2}\n"
        f"{card_line_3}\n"
        f"{card_line_4}\n"
        f"╚════════════════════════════════════════╝\n"
        f"```\n"
        f"🧭 **BOARD SUGGESTION**\n"
        f"> *\"{data['next_suggested_action']}\"*"
    )
    
    # Custom IDs
    squad_id = encode_custom_id("locker", "view", "squad", nonce)
    players_id = encode_custom_id("player", "view", "search", nonce)
    dashboard_id = encode_custom_id("locker", "open", "club", nonce)
    help_id = encode_custom_id("locker", "view", "help", nonce)
    lineup_id = encode_custom_id("lineup", "open", "main", nonce)
    
    comp_payload = []
    if has_image:
        comp_payload.append(media_gallery(["attachment://club_locker.png"], ["Locker Room Dashboard"]))
    else:
        comp_payload.append(
            container([
                text_display(text)
            ])
        )
        
    comp_payload.extend([
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
    ])
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

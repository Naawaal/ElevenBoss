# app/ui/layouts/setup.py

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

def build_setup_layout(config, is_admin: bool, nonce: str) -> V2View:
    """
    Builds the ElevenBoss Setup configuration control panel.
    """
    mode = "AUTOMATION MODE: ENABLED" if (config.auto_join_draft_league or config.auto_start_league or config.matchday_enabled) else "AUTOMATION MODE: MANUAL FALLBACK ONLY"
    
    text = (
        f"###⚙️ ELEVENBOSS SERVER SETUP\n"
        f"**Mode:** `{mode}`\n\n"
        f"🤖 **Auto-Join Draft League:** `{'ENABLED' if config.auto_join_draft_league else 'DISABLED'}`\n"
        f"🚀 **Auto-Start League:** `{'ENABLED' if config.auto_start_league else 'DISABLED'}`\n"
        f"👥 **Min Human Clubs:** `{config.minimum_human_clubs}`\n"
        f"🤖 **Auto-Fill Bot Clubs:** `{'ENABLED' if config.auto_fill_with_bot_clubs else 'DISABLED'}`\n"
        f"📅 **Matchday Schedule:** `{'ENABLED' if config.matchday_enabled else 'DISABLED'}`\n"
        f"📢 **Announcement Channel:** <#{config.matchday_announcement_channel_id or config.game_channel_id or 'None'}>\n"
    )

    # Calculate next action prediction string
    if config.auto_start_league:
        text += "\n*Next Lifecycle Action:* Automatically start the league when draft requirements are met.\n"
    else:
        text += "\n*Next Lifecycle Action:* Waiting for manual league start command.\n"

    # Custom IDs
    toggle_join_id = encode_custom_id("setup", "automation", "toggle_join", nonce)
    toggle_start_id = encode_custom_id("setup", "automation", "toggle_start", nonce)
    toggle_sched_id = encode_custom_id("setup", "automation", "toggle_sched", nonce)
    refresh_id = encode_custom_id("setup", "refresh", "main", nonce)

    rows = []
    
    if is_admin:
        join_btn_label = "Disable Auto Join" if config.auto_join_draft_league else "Enable Auto Join"
        start_btn_label = "Disable Auto Start" if config.auto_start_league else "Enable Auto Start"
        sched_btn_label = "Disable Schedule" if config.matchday_enabled else "Enable Schedule"

        rows.append(action_row([
            primary_button(join_btn_label, toggle_join_id),
            primary_button(start_btn_label, toggle_start_id),
            primary_button(sched_btn_label, toggle_sched_id)
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

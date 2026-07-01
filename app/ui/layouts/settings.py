# app/ui/layouts/settings.py

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

def build_settings_overview_layout(
    config,
    league_status: str,
    season_week: str,
    next_run_str: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders the Settings Overview panel using Components V2.
    """
    admin_role_mention = f"<@&{config.admin_role_id}>" if config.admin_role_id else "`None`"
    
    text = (
        f"###⚙️ ELEVENBOSS SERVER SETTINGS OVERVIEW\n\n"
        f"🌐 **Current League status:** `{league_status}` | `{season_week}`\n\n"
        f"📺 **Game Channel:** <#{config.game_channel_id or 'None'}>\n"
        f"📢 **Announcement Channel:** <#{config.matchday_announcement_channel_id or 'None'}>\n"
        f"🛡️ **Admin Role:** {admin_role_mention}\n\n"
        f"🤖 **Auto Join Draft:** `{'ENABLED' if config.auto_join_draft_league else 'DISABLED'}`\n"
        f"🚀 **Auto Start League:** `{'ENABLED' if config.auto_start_league else 'DISABLED'}` (Min Humans: `{config.minimum_human_clubs}`)\n"
        f"📅 **Matchday Schedule:** `{'ENABLED' if config.matchday_enabled else 'DISABLED'}` (`Every {config.matchday_day or 'None'} at {config.matchday_time or 'None'} {config.matchday_timezone}`)\n"
        f"⏭️ **Next Automation Action:** `{next_run_str}`\n"
    )

    # Encode custom IDs
    go_channels_id = encode_custom_id("settings", "view", "channels", nonce)
    go_admin_role_id = encode_custom_id("settings", "view", "admin_role", nonce)
    go_automation_id = encode_custom_id("settings", "view", "automation", nonce)
    go_schedule_id = encode_custom_id("settings", "view", "schedule", nonce)
    go_matchday_id = encode_custom_id("settings", "view", "matchday", nonce)
    refresh_id = encode_custom_id("settings", "refresh", "overview", nonce)

    rows = []
    
    # Navigation Buttons row 1
    # Settings category tabs
    rows.append(action_row([
        secondary_button("📺 Channels", go_channels_id),
        secondary_button("🛡️ Admin Role", go_admin_role_id),
        secondary_button("🤖 Automation", go_automation_id),
    ]))
    
    rows.append(action_row([
        secondary_button("📅 Schedule", go_schedule_id),
        secondary_button("⚽ Matchday", go_matchday_id),
        secondary_button("🔄 Refresh", refresh_id),
        close_button(nonce)
    ]))

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)

    return V2View(comp_payload)

def build_settings_channels_layout(config, is_admin: bool, nonce: str) -> V2View:
    """
    Renders the Channels view panel.
    """
    text = (
        f"###📺 ELEVENBOSS CHANNELS CONFIGURATION\n\n"
        f"🎮 **Game Channel:** <#{config.game_channel_id or 'None'}>\n"
        f"📢 **Matchday Announcement Channel:** <#{config.matchday_announcement_channel_id or 'None'}>\n"
        f"🗂️ **Logs Channel:** `Disabled` (Standard terminal/file logging active)\n\n"
        f"*Use `/settings channels set` to update these configurations.*"
    )

    back_id = encode_custom_id("settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("settings", "view", "channels", nonce)

    rows = [
        action_row([
            secondary_button("⬅️ Back to Overview", back_id),
            secondary_button("🔄 Refresh", refresh_id),
            close_button(nonce)
        ])
    ]

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

def build_settings_admin_role_layout(config, is_admin: bool, nonce: str) -> V2View:
    """
    Renders the Admin Role view panel.
    """
    role_str = f"<@&{config.admin_role_id}>" if config.admin_role_id else "`None`"
    text = (
        f"###🛡️ ELEVENBOSS ADMIN ROLE CONFIGURATION\n\n"
        f"👥 **Current ElevenBoss Admin Role:** {role_str}\n\n"
        f"🔒 **Permissions Model:**\n"
        f"• *Discord Administrators* can view/change/clear the admin role.\n"
        f"• Users with this role can run `/settings` config commands (except changing the admin role) and `/admin` recovery commands.\n"
        f"• Normal users can only view read-only configuration metrics.\n\n"
        f"*Use `/settings admin-role set` or `/settings admin-role clear` to modify.*"
    )

    back_id = encode_custom_id("settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("settings", "view", "admin_role", nonce)

    rows = [
        action_row([
            secondary_button("⬅️ Back to Overview", back_id),
            secondary_button("🔄 Refresh", refresh_id),
            close_button(nonce)
        ])
    ]

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

def build_settings_automation_layout(config, is_admin: bool, nonce: str) -> V2View:
    """
    Renders the Automation configuration panel.
    """
    deadline_str = config.registration_deadline.strftime("%Y-%m-%d %H:%M:%S UTC") if config.registration_deadline else "None"
    last_run = config.last_automation_run_at.strftime("%Y-%m-%d %H:%M:%S UTC") if config.last_automation_run_at else "Never"
    
    text = (
        f"###🤖 ELEVENBOSS LEAGUE AUTOMATION\n\n"
        f"🔗 **Auto-Join Draft League:** `{'ENABLED' if config.auto_join_draft_league else 'DISABLED'}`\n"
        f"🚀 **Auto-Start League:** `{'ENABLED' if config.auto_start_league else 'DISABLED'}`\n"
        f"🤖 **Auto-Fill Bot Clubs:** `{'ENABLED' if config.auto_fill_with_bot_clubs else 'DISABLED'}`\n"
        f"👥 **Minimum Human Clubs:** `{config.minimum_human_clubs}`\n"
        f"⏳ **Registration Deadline:** `{deadline_str}`\n\n"
        f"⚡ **Automation Running Status:** `{config.automation_status.upper() if config.automation_status else 'IDLE'}`\n"
        f"⏱️ **Last Automation Run:** `{last_run}`\n"
        f"🏁 **Last Automation Status:** `{config.last_automation_status or 'None'}`\n"
    )
    if config.last_automation_error:
        text += f"⚠️ **Last Error Summary:** `{config.last_automation_error[:80]}`\n"

    back_id = encode_custom_id("settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("settings", "view", "automation", nonce)

    rows = [
        action_row([
            secondary_button("⬅️ Back to Overview", back_id),
            secondary_button("🔄 Refresh", refresh_id),
            close_button(nonce)
        ])
    ]

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

def build_settings_schedule_layout(config, next_run_str: str, is_admin: bool, nonce: str) -> V2View:
    """
    Renders the Matchday schedule configuration panel.
    """
    status_label = "🟢 ENABLED" if config.matchday_enabled else "🔴 DISABLED"
    text = (
        f"###📅 MATCHDAY SCHEDULE CONFIGURATION\n\n"
        f"**Schedule State:** `{status_label}`\n\n"
        f"📅 **Matchday Day:** `{config.matchday_day or 'None'}`\n"
        f"🕒 **Matchday Time:** `{config.matchday_time or 'None'}`\n"
        f"🌍 **Matchday Timezone:** `{config.matchday_timezone}`\n"
        f"⏭️ **Next Scheduled Run:** `{next_run_str}`\n"
    )

    enable_id = encode_custom_id("schedule", "enable", "main", nonce)
    disable_id = encode_custom_id("schedule", "disable", "main", nonce)
    back_id = encode_custom_id("settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("settings", "view", "schedule", nonce)

    rows = []
    if is_admin:
        toggle_buttons = []
        if not config.matchday_enabled:
            toggle_buttons.append(primary_button("🟢 Enable Schedule", enable_id))
        else:
            toggle_buttons.append(secondary_button("🔴 Disable Schedule", disable_id))
        rows.append(action_row(toggle_buttons))

    rows.append(action_row([
        secondary_button("⬅️ Back to Overview", back_id),
        secondary_button("🔄 Refresh", refresh_id),
        close_button(nonce)
    ]))

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

def build_settings_matchday_layout(
    config,
    league_status: str,
    season_week: str,
    fixtures_stats: dict,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders the Matchday automation state.
    """
    total = fixtures_stats.get("total", 0)
    scheduled = fixtures_stats.get("scheduled", 0)
    played = fixtures_stats.get("played", 0)
    
    text = (
        f"###⚽ MATCHDAY AUTOMATION STATE\n\n"
        f"🏆 **Active League:** `{league_status}`\n"
        f"📅 **Active Season:** `{season_week}`\n\n"
        f"📊 **Fixture Statistics:**\n"
        f"• **Total Fixtures:** `{total}`\n"
        f"• **Scheduled:** `{scheduled}`\n"
        f"• **Played:** `{played}`\n\n"
        f"⚙️ **Schedule Runner:** `{'ENABLED' if config.matchday_enabled else 'DISABLED'}`\n"
    )

    back_id = encode_custom_id("settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("settings", "view", "matchday", nonce)

    rows = [
        action_row([
            secondary_button("⬅️ Back to Overview", back_id),
            secondary_button("🔄 Refresh", refresh_id),
            close_button(nonce)
        ])
    ]

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

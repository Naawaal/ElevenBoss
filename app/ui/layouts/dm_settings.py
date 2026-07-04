# app/ui/layouts/dm_settings.py

from datetime import datetime
from app.ui.components import (
    container,
    text_display,
    action_row,
    primary_button,
    secondary_button,
    select_menu,
    V2View,
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button

def build_dm_server_picker(guild_views, nonce: str) -> V2View:
    """
    Renders the server picker dropdown for DM admin settings.
    """
    text = (
        "### ⚙️ ELEVENBOSS ADMIN CONSOLE\n"
        "Select a server to manage from the dropdown below:"
    )

    options = [
        {
            "label": g.guild_name,
            "value": str(g.guild_id),
            "description": g.permission_label
        }
        for g in guild_views
    ]

    select_id = encode_custom_id("dm_settings", "guild_select", "main", nonce)
    
    comp_payload = [
        container([text_display(text)]),
        action_row([
            select_menu(select_id, options, placeholder="Select a server to manage...")
        ]),
        action_row([
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

def build_settings_overview_layout(
    config,
    guild_name: str,
    league_status: str,
    season_week: str,
    next_run_str: str,
    admin_role_name: str,
    mention_role_name: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders the settings overview for the selected guild.
    """
    deadline_str = config.registration_deadline.strftime("%Y-%m-%d %H:%M UTC") if config.registration_deadline else "None"
    
    text = (
        f"### ⚙️ ELEVENBOSS SETTINGS — {guild_name.upper()}\n\n"
        f"🌐 **Current League Status:** `{league_status}` | `{season_week}`\n\n"
        f"🎮 **Game Channel:** <#{config.game_channel_id or 'None'}>\n"
        f"📢 **Announcement Channel:** <#{config.matchday_announcement_channel_id or 'None'}>\n"
        f"🛡️ **Admin Role:** `{admin_role_name}`\n"
        f"🔔 **Announcement Mention:** `{mention_role_name}`\n\n"
        f"🤖 **Auto Join Draft:** `{'ENABLED' if config.auto_join_draft_league else 'DISABLED'}`\n"
        f"🚀 **Auto Start League:** `{'ENABLED' if config.auto_start_league else 'DISABLED'}` (Min Humans: `{config.minimum_human_clubs}`)\n"
        f"⏳ **Registration Deadline:** `{deadline_str}`\n\n"
        f"📅 **Matchday Schedule:** `{'ENABLED' if config.matchday_enabled else 'DISABLED'}` (`Every {config.matchday_day or 'None'} at {config.matchday_time or 'None'} {config.matchday_timezone}`)\n"
        f"⏭️ **Next Automation Action:** `{next_run_str}`\n"
    )

    go_channels_id = encode_custom_id("dm_settings", "view", "channels", nonce)
    go_admin_role_id = encode_custom_id("dm_settings", "view", "admin_role", nonce)
    go_automation_id = encode_custom_id("dm_settings", "view", "automation", nonce)
    go_schedule_id = encode_custom_id("dm_settings", "view", "schedule", nonce)
    go_matchday_id = encode_custom_id("dm_settings", "view", "matchday", nonce)
    switch_id = encode_custom_id("dm_settings", "switch", "guild", nonce)
    refresh_id = encode_custom_id("dm_settings", "view", "overview", nonce)

    rows = [
        action_row([
            secondary_button("📺 Channels", go_channels_id),
            secondary_button("🛡️ Admin Role", go_admin_role_id),
            secondary_button("🤖 Automation", go_automation_id),
        ]),
        action_row([
            secondary_button("📅 Schedule", go_schedule_id),
            secondary_button("⚽ Matchday", go_matchday_id),
            secondary_button("🔄 Switch Server", switch_id),
        ]),
        action_row([
            secondary_button("🔄 Refresh", refresh_id),
            close_button(nonce)
        ])
    ]

    comp_payload = [
        container([text_display(text)]),
    ]
    comp_payload.extend(rows)
    return V2View(comp_payload)

def build_settings_channels_layout(
    config,
    guild_name: str,
    guild_channels,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders the channel settings view with dropdown config select menus.
    """
    text = (
        f"### 📺 ELEVENBOSS CHANNELS — {guild_name.upper()}\n\n"
        f"🎮 **Game Channel:** <#{config.game_channel_id or 'None'}>\n"
        f"📢 **Matchday Announcement Channel:** <#{config.matchday_announcement_channel_id or 'None'}>\n\n"
        f"*Select a text channel from the dropdown menus below to update.*"
    )

    back_id = encode_custom_id("dm_settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("dm_settings", "view", "channels", nonce)
    
    # Text channel options for the select menus
    options = [
        {"label": f"#{c.name}", "value": str(c.id)}
        for c in guild_channels[:25]
    ]

    game_select_id = encode_custom_id("dm_settings", "channel_game", "select", nonce)
    match_select_id = encode_custom_id("dm_settings", "channel_match", "select", nonce)

    rows = []
    if is_admin and options:
        rows.append(action_row([
            select_menu(game_select_id, options, placeholder="Set Game Channel...")
        ]))
        rows.append(action_row([
            select_menu(match_select_id, options, placeholder="Set Matchday Announcement Channel...")
        ]))

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

def build_settings_admin_role_layout(
    config,
    guild_name: str,
    guild_roles,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders ElevenBoss roles and mention settings with select dropdowns.
    """
    admin_role_name = f"ID: {config.admin_role_id}" if config.admin_role_id else "None"
    mention_role_name = f"ID: {config.mention_role_id}" if getattr(config, "mention_role_id", None) else "None"
    for r in guild_roles:
        if str(r.id) == str(config.admin_role_id):
            admin_role_name = f"@{r.name}"
        if str(r.id) == str(getattr(config, "mention_role_id", None)):
            mention_role_name = f"@{r.name}"

    text = (
        f"### 🛡️ ROLE SETTINGS — {guild_name.upper()}\n\n"
        f"👥 **Admin Role:** `{admin_role_name}`\n"
        f"🔔 **Announcement Mention Role:** `{mention_role_name}`\n\n"
        f"🔒 **Permissions Model:**\n"
        f"• *Discord Administrators* can configure or clear these roles.\n"
        f"• Members with the Admin role can manage settings and run `/admin` commands in DMs.\n"
        f"• The Announcement Mention Role will be mentioned whenever a league announcement is sent.\n"
    )

    back_id = encode_custom_id("dm_settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("dm_settings", "view", "admin_role", nonce)

    role_select_id = encode_custom_id("dm_settings", "role_admin", "select", nonce)
    mention_select_id = encode_custom_id("dm_settings", "role_mention", "select", nonce)

    role_options = [
        {"label": f"@{r.name}", "value": str(r.id)}
        for r in guild_roles[:24]
    ]
    role_options.append({"label": "❌ Clear Admin Role", "value": "clear", "description": "Removes the admin role requirement."})

    mention_options = [
        {"label": f"@{r.name}", "value": str(r.id)}
        for r in guild_roles[:24]
    ]
    mention_options.append({"label": "❌ Clear Mention Role", "value": "clear", "description": "Removes the announcement mention."})

    rows = []
    if is_admin:
        rows.append(action_row([
            select_menu(role_select_id, role_options, placeholder="Select Admin Role...")
        ]))
        rows.append(action_row([
            select_menu(mention_select_id, mention_options, placeholder="Select Announcement Mention Role...")
        ]))

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

def build_settings_automation_layout(
    config,
    guild_name: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders league automation config parameters.
    """
    deadline_str = config.registration_deadline.strftime("%Y-%m-%d %H:%M UTC") if config.registration_deadline else "None"
    last_run = config.last_automation_run_at.strftime("%Y-%m-%d %H:%M UTC") if config.last_automation_run_at else "Never"
    
    text = (
        f"### 🤖 LEAGUE AUTOMATION — {guild_name.upper()}\n\n"
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

    back_id = encode_custom_id("dm_settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("dm_settings", "view", "automation", nonce)

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

def build_settings_schedule_layout(
    config,
    guild_name: str,
    next_run_str: str,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders matchday scheduling config parameters.
    """
    status_label = "🟢 ENABLED" if config.matchday_enabled else "🔴 DISABLED"
    text = (
        f"### 📅 MATCHDAY SCHEDULE — {guild_name.upper()}\n\n"
        f"**Schedule State:** `{status_label}`\n\n"
        f"📅 **Matchday Day:** `{config.matchday_day or 'None'}`\n"
        f"🕒 **Matchday Time:** `{config.matchday_time or 'None'}`\n"
        f"🌍 **Matchday Timezone:** `{config.matchday_timezone}`\n"
        f"⏭️ **Next Scheduled Run:** `{next_run_str}`\n"
    )

    enable_id = encode_custom_id("schedule", "enable", "main", nonce)
    disable_id = encode_custom_id("schedule", "disable", "main", nonce)
    edit_id = encode_custom_id("schedule", "open_modal", "setup", nonce)
    back_id = encode_custom_id("dm_settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("dm_settings", "view", "schedule", nonce)

    rows = []
    if is_admin:
        toggle_buttons = []
        if not config.matchday_enabled:
            toggle_buttons.append(primary_button("🟢 Enable Schedule", enable_id))
        else:
            toggle_buttons.append(secondary_button("🔴 Disable Schedule", disable_id))
        toggle_buttons.append(primary_button("📝 Configure Schedule", edit_id))
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
    guild_name: str,
    league_status: str,
    season_week: str,
    fixtures_stats: dict,
    is_admin: bool,
    nonce: str
) -> V2View:
    """
    Renders matchday stats and fixtures progress.
    """
    total = fixtures_stats.get("total", 0)
    scheduled = fixtures_stats.get("scheduled", 0)
    played = fixtures_stats.get("played", 0)
    
    text = (
        f"### ⚽ MATCHDAY AUTOMATION STATE — {guild_name.upper()}\n\n"
        f"🏆 **Active League:** `{league_status}`\n"
        f"📅 **Active Season:** `{season_week}`\n\n"
        f"📊 **Fixture Statistics:**\n"
        f"• **Total Fixtures:** `{total}`\n"
        f"• **Scheduled:** `{scheduled}`\n"
        f"• **Played:** `{played}`\n\n"
        f"⚙️ **Schedule Runner:** `{'ENABLED' if config.matchday_enabled else 'DISABLED'}`\n"
    )

    back_id = encode_custom_id("dm_settings", "view", "overview", nonce)
    refresh_id = encode_custom_id("dm_settings", "view", "matchday", nonce)

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

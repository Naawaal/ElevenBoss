from app.ui.components import container, text_display, action_row, primary_button, secondary_button, success_button, media_gallery, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button

def build_league_dashboard_layout(data, nonce: str, is_admin: bool, banner: str | None = None, has_image: bool = False) -> V2View:
    """
    Builds the League Dashboard UI using Discord Components V2.
    """
    status_emoji = "📝" if data.status == "draft" else "⚔️"
    
    text = (
        f"### {status_emoji} LEAGUE DASHBOARD — {data.league_name}\n"
        f"📈 **Status:** `{data.status.upper()}`\n"
        f"👥 **League Size:** {data.max_clubs} clubs\n"
        f"👤 **Human Clubs Joined:** {data.human_clubs} / {data.max_clubs}\n"
        f"🤖 **Bot Filler Clubs:** {data.bot_clubs}\n"
        f"📊 **Total Clubs:** {data.total_clubs} / {data.max_clubs}\n"
    )
    
    if data.season_number is not None:
        text += f"📅 **Current Season:** Season {data.season_number}\n"
    if data.current_week is not None:
        text += f"⏱️ **Current Week:** Week {data.current_week}\n"
        
    text += f"\n🧭 **Next Action:** {data.next_action}"
    
    # Encode custom IDs
    join_id = encode_custom_id("league", "join", "main", nonce)
    start_id = encode_custom_id("league", "start", "main", nonce)
    view_table_id = encode_custom_id("league", "view_table", "main", nonce)
    back_id = encode_custom_id("nav", "back", "locker", nonce)
    
    # Rows construction
    rows = []
    
    # Row 1: Interactive league actions
    action_buttons = []
    
    if data.status == "draft":
        # Join button only shown/enabled in draft status
        action_buttons.append(success_button("📥 Join League", join_id, disabled=not data.can_join))
        
        # Start button only shown/enabled for admin in draft status
        if is_admin:
            action_buttons.append(primary_button("🚀 Start League", start_id, disabled=not data.can_start))
        else:
            action_buttons.append(primary_button("🚀 Start League", start_id, disabled=True))
    else:
        # If league is active, don't show Join, and disable Start
        if is_admin:
            action_buttons.append(primary_button("🚀 Start League", start_id, disabled=True))
            
    if action_buttons:
        rows.append(action_row(action_buttons))
        
    # Row 2: Navigation & Table
    nav_buttons = []
    if data.status == "active":
        view_fixtures_id = encode_custom_id("fixtures", "view", "current", nonce)
        nav_buttons.append(success_button("📅 View Fixtures", view_fixtures_id))

    nav_buttons.append(
        primary_button("📊 View Table", view_table_id)
        if data.status == "active"
        else success_button("📊 View Table", view_table_id)
    )
    nav_buttons.append(refresh_button("league", "refresh", nonce))
    nav_buttons.append(secondary_button("◀ Back", back_id))
    nav_buttons.append(close_button(nonce))
    rows.append(action_row(nav_buttons))

    
    # Assemble final layout payload
    comp_payload = []
    
    # If a success/error notification banner exists, prepend it first
    if banner:
        comp_payload.append(
            container([
                text_display(banner)
            ])
        )
        
    if has_image:
        comp_payload.append(media_gallery(["attachment://league.png"], ["League Dashboard Status"]))
    else:
        comp_payload.append(
            container([
                text_display(text)
            ])
        )
        
    comp_payload.extend(rows)
    
    return V2View(comp_payload)

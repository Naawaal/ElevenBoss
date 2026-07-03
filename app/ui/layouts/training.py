# app/ui/layouts/training.py

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
from app.services.training_service import ClubTrainingOverviewResult


def build_training_dashboard_layout(
    data: ClubTrainingOverviewResult, nonce: str, success_msg: str | None = None
) -> V2View:
    """
    Builds the main Training Overview Dashboard.
    """
    lines = []
    if success_msg:
        lines.append(f"✅ {success_msg}\n")

    lines.append(f"🏋️ **Training — {data.club_name}**\n")
    lines.append(
        f"**Default Plan:** `{data.default_plan}`  |  "
        f"**Intensity:** `{data.intensity}`  |  "
        f"**Week:** `{data.week}`\n"
    )

    lines.append("── **Condition Summary** ──────────────────")
    lines.append(f"• Low Sharpness (<40): `{data.low_sharpness_count} players`")
    lines.append(f"• Low Morale (<30): `{data.low_morale_count} players`")
    lines.append(f"• Squad Avg Readiness: `{data.avg_readiness:.2f}x` (multiplies match fitness)\n")

    lines.append("── **Development Outlook** ────────────────")
    # Show top 5 players in the outlook for space
    for name, avg_xp, projected in data.development_outlook[:5]:
        indicator = "★" if "track for +2" in projected else "●" if "track for +1" in projected else "▲" if "potential" in projected else "○"
        lines.append(f"{indicator} **{name}**: Avg `{avg_xp:.1f} XP/wk` → *{projected}*")
    
    if len(data.development_outlook) > 5:
        lines.append(f"*...and {len(data.development_outlook) - 5} more players (view via Outlook)*")

    text = "\n".join(lines)

    # Custom IDs
    intensity_id = encode_custom_id("training", "open", "intensity", nonce)
    plan_id = encode_custom_id("training", "open", "default_plan", nonce)
    player_plans_id = encode_custom_id("training", "open", "player_plans", nonce)
    condition_id = encode_custom_id("training", "open", "condition", nonce)
    outlook_id = encode_custom_id("training", "open", "outlook", nonce)
    back_id = encode_custom_id("locker", "open", "club", nonce)

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            primary_button("Set Intensity", intensity_id),
            primary_button("Default Plan", plan_id),
            primary_button("Player Plans", player_plans_id),
        ]),
        action_row([
            secondary_button("Condition Report", condition_id),
            secondary_button("Outlook Report", outlook_id),
        ]),
        action_row([
            secondary_button("◀ Back to Locker Room", back_id),
            close_button(nonce),
        ])
    ]

    return V2View(comp_payload)


def build_training_intensity_layout(intensity: str, nonce: str) -> V2View:
    """
    Layout to configure training intensity for the club.
    """
    text = (
        "🏋️ **Configure Training Intensity**\n\n"
        f"Current Intensity: `{intensity.title()}`\n\n"
        "Intensity levels affect weekly training outcomes:\n"
        "• **Light**: safest. XP `×0.75`, Morale `+1`, Readiness `+0.01`.\n"
        "• **Normal**: standard. XP `×1.00`, Morale `0`, Readiness `0`.\n"
        "• **Heavy**: risky. XP `×1.25`, Morale `-2`, Readiness `-0.02`.\n\n"
        "Select the intensity level below:"
    )

    options = [
        {"label": "Light Intensity", "value": "light", "description": "XP ×0.75, Morale +1, Readiness +0.01"},
        {"label": "Normal Intensity", "value": "normal", "description": "XP ×1.00, Morale +0, Readiness +0.00"},
        {"label": "Heavy Intensity", "value": "heavy", "description": "XP ×1.25, Morale -2, Readiness -0.02"},
    ]

    select_id = encode_custom_id("training", "set_intensity", "select", nonce)
    back_id = encode_custom_id("training", "view", "overview", nonce)

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            select_menu(select_id, options, placeholder="Choose intensity...")
        ]),
        action_row([
            secondary_button("◀ Back to Overview", back_id),
            close_button(nonce)
        ])
    ]

    return V2View(comp_payload)


def build_training_default_plan_layout(default_plan: str, nonce: str) -> V2View:
    """
    Layout to configure the default training plan for the club.
    """
    text = (
        "📋 **Configure Club Default Plan**\n\n"
        f"Current Default Plan: `{default_plan.title()}`\n\n"
        "The default plan is applied to players who do not have an individual plan assigned:\n"
        "• **Balanced**: Safe all-round plan. XP `8`, Sharpness `+2`, Morale `+1`, Readiness `+0.00`.\n"
        "• **Fitness**: Better match readiness. XP `4`, Sharpness `+0`, Morale `+0`, Readiness `+0.03`.\n"
        "• **Sharpness**: Stronger short-term performance. XP `6`, Sharpness `+5`, Morale `-1`, Readiness `+0.02`.\n"
        "• **Tactical**: Best development XP. XP `10`, Sharpness `+1`, Morale `+3`, Readiness `+0.00`.\n\n"
        "Select the default training plan below:"
    )

    options = [
        {"label": "Balanced Plan", "value": "balanced", "description": "XP 8, Sharpness +2, Morale +1, Readiness +0.00"},
        {"label": "Fitness Plan", "value": "fitness", "description": "XP 4, Sharpness +0, Morale +0, Readiness +0.03"},
        {"label": "Sharpness Plan", "value": "sharpness", "description": "XP 6, Sharpness +5, Morale -1, Readiness +0.02"},
        {"label": "Tactical Plan", "value": "tactical", "description": "XP 10, Sharpness +1, Morale +3, Readiness +0.00"},
    ]

    select_id = encode_custom_id("training", "set_default_plan", "select", nonce)
    back_id = encode_custom_id("training", "view", "overview", nonce)

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            select_menu(select_id, options, placeholder="Choose default plan...")
        ]),
        action_row([
            secondary_button("◀ Back to Overview", back_id),
            close_button(nonce)
        ])
    ]

    return V2View(comp_payload)


def build_player_plans_layout(
    players: list, dev_states: dict, default_plan: str, nonce: str, page: int = 1
) -> V2View:
    """
    Layout displaying all players and their active training plans.
    Allows choosing a player to assign them an individual plan.
    """
    per_page = 8
    total_pages = max(1, (len(players) + per_page - 1) // per_page)
    page = max(1, min(total_pages, page))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_players = players[start_idx:end_idx]

    lines = [
        "🏃 **Squad Player Plans**\n",
        f"Select a player from the dropdown to assign them a customized training plan. "
        f"Players without an assigned plan default to the club's plan: `{default_plan.title()}`.\n"
    ]

    select_options = []
    for p in page_players:
        state = dev_states.get(p.id)
        assigned_plan = state.plan_type.title() if (state and state.plan_type) else "Balanced (Default)"
        lines.append(f"• **{p.display_name}** ({p.position}, OVR {p.overall})")
        lines.append(f"  └─ Plan: `{assigned_plan}`")
        
        select_options.append({
            "label": f"{p.display_name} ({p.position})",
            "value": str(p.id),
            "description": f"Currently on {assigned_plan}"
        })
    
    lines.append(f"\nPage `{page}` of `{total_pages}`")
    text = "\n".join(lines)

    select_id = encode_custom_id("training", "open", "set_player_plan", nonce)
    back_id = encode_custom_id("training", "view", "overview", nonce)
    
    # Paginated buttons
    nav_buttons = []
    if page > 1:
        prev_id = encode_custom_id("training", "open_plans_page", str(page - 1), nonce)
        nav_buttons.append(secondary_button("◀ Prev Page", prev_id))
    if page < total_pages:
        next_id = encode_custom_id("training", "open_plans_page", str(page + 1), nonce)
        nav_buttons.append(secondary_button("Next Page ▶", next_id))

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            select_menu(select_id, select_options, placeholder="Select player to edit plan...")
        ]),
        action_row(nav_buttons) if nav_buttons else None,
        action_row([
            secondary_button("◀ Back to Overview", back_id),
            close_button(nonce)
        ])
    ]
    
    # Filter out empty rows
    comp_payload = [c for c in comp_payload if c is not None]

    return V2View(comp_payload)


def build_set_player_plan_layout(player, current_plan: str, nonce: str) -> V2View:
    """
    Layout to assign an individual plan to a player.
    """
    text = (
        f"🏃 **Set Plan for {player.display_name}**\n"
        f"Position: `{player.position}`  |  OVR: `{player.overall}`\n\n"
        f"Current assigned plan: `{current_plan.title()}`\n\n"
        "Plans affect weekly training deltas for this player:\n"
        "• **Balanced**: XP `8`, Sharpness `+2`, Morale `+1`, Readiness `+0.00`.\n"
        "• **Fitness**: XP `4`, Sharpness `+0`, Morale `+0`, Readiness `+0.03`.\n"
        "• **Sharpness**: XP `6`, Sharpness `+5`, Morale `-1`, Readiness `+0.02`.\n"
        "• **Tactical**: XP `10`, Sharpness `+1`, Morale `+3`, Readiness `+0.00`.\n\n"
        "Select the plan type below:"
    )

    options = [
        {"label": "Balanced Plan", "value": "balanced", "description": "XP 8, Sharpness +2, Morale +1, Readiness +0.00"},
        {"label": "Fitness Plan", "value": "fitness", "description": "XP 4, Sharpness +0, Morale +0, Readiness +0.03"},
        {"label": "Sharpness Plan", "value": "sharpness", "description": "XP 6, Sharpness +5, Morale -1, Readiness +0.02"},
        {"label": "Tactical Plan", "value": "tactical", "description": "XP 10, Sharpness +1, Morale +3, Readiness +0.00"},
    ]

    select_id = encode_custom_id("training", "set_player_plan", str(player.id), nonce)
    back_id = encode_custom_id("training", "open", "player_plans", nonce)

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            select_menu(select_id, options, placeholder="Select training plan...")
        ]),
        action_row([
            secondary_button("◀ Back to Player Plans", back_id),
            close_button(nonce)
        ])
    ]

    return V2View(comp_payload)


def build_training_condition_layout(
    players: list, dev_states: dict, nonce: str, page: int = 1
) -> V2View:
    """
    Renders the squad condition report (Fitness, Sharpness, Morale, Readiness).
    """
    per_page = 8
    total_pages = max(1, (len(players) + per_page - 1) // per_page)
    page = max(1, min(total_pages, page))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_players = players[start_idx:end_idx]

    lines = [
        "📊 **Squad Condition Report**\n",
        "Readiness acts as a temporary fitness multiplier inside the match engine. "
        "High sharpness and fitness maximize performance.\n",
        "| Player | Fit | Sharp | Morale | Readiness |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]

    for p in page_players:
        state = dev_states.get(p.id)
        readiness = float(state.readiness_modifier) if state else 1.00
        lines.append(f"| {p.display_name} | {p.fitness} | {p.sharpness} | {p.morale} | {readiness:.2f}x |")

    lines.append(f"\nPage `{page}` of `{total_pages}`")
    text = "\n".join(lines)

    back_id = encode_custom_id("training", "view", "overview", nonce)
    
    nav_buttons = []
    if page > 1:
        prev_id = encode_custom_id("training", "open_condition_page", str(page - 1), nonce)
        nav_buttons.append(secondary_button("◀ Prev Page", prev_id))
    if page < total_pages:
        next_id = encode_custom_id("training", "open_condition_page", str(page + 1), nonce)
        nav_buttons.append(secondary_button("Next Page ▶", next_id))

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row(nav_buttons) if nav_buttons else None,
        action_row([
            secondary_button("◀ Back to Overview", back_id),
            close_button(nonce)
        ])
    ]
    
    comp_payload = [c for c in comp_payload if c is not None]

    return V2View(comp_payload)


def build_training_outlook_layout(
    outlook_data: list, nonce: str, page: int = 1
) -> V2View:
    """
    Renders the season-end training outlook for all players.
    """
    per_page = 8
    total_pages = max(1, (len(outlook_data) + per_page - 1) // per_page)
    page = max(1, min(total_pages, page))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_outlook = outlook_data[start_idx:end_idx]

    lines = [
        "📈 **Season-End Development Outlook**\n",
        "Shows average weekly XP earned (training + matches) and the projected "
        "season-end OVR bonus (+0, +1, or +2 OVR) capped by potential.\n"
    ]

    for name, avg_xp, projected in page_outlook:
        indicator = "★" if "track for +2" in projected else "●" if "track for +1" in projected else "▲" if "potential" in projected else "○"
        lines.append(f"{indicator} **{name}**")
        lines.append(f"  └─ Avg: `{avg_xp:.1f} XP/wk`  |  *Projected: {projected}*")

    lines.append(f"\nPage `{page}` of `{total_pages}`")
    text = "\n".join(lines)

    back_id = encode_custom_id("training", "view", "overview", nonce)
    
    nav_buttons = []
    if page > 1:
        prev_id = encode_custom_id("training", "open_outlook_page", str(page - 1), nonce)
        nav_buttons.append(secondary_button("◀ Prev Page", prev_id))
    if page < total_pages:
        next_id = encode_custom_id("training", "open_outlook_page", str(page + 1), nonce)
        nav_buttons.append(secondary_button("Next Page ▶", next_id))

    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row(nav_buttons) if nav_buttons else None,
        action_row([
            secondary_button("◀ Back to Overview", back_id),
            close_button(nonce)
        ])
    ]
    
    comp_payload = [c for c in comp_payload if c is not None]

    return V2View(comp_payload)

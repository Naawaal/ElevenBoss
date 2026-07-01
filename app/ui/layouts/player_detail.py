from app.ui.components import container, text_display, action_row, select_menu, V2View
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button, refresh_button, back_button
from app.ui.formatters import format_money, format_progress_bar

def build_player_detail_layout(player: dict, nonce: str) -> V2View:
    """
    Builds the Player Detail layout.
    """
    value_str = format_money(player["value"])
    wage_str = f"{format_money(player['wage'])}/wk"
    
    fitness_bar = format_progress_bar(player["fitness"])
    sharpness_bar = format_progress_bar(player["sharpness"])
    morale_bar = format_progress_bar(player["morale"])
    
    traits_list = player["traits"].get("list", []) if isinstance(player["traits"], dict) else []
    traits_str = ", ".join(t.replace("_", " ").title() for t in traits_list) if traits_list else "None"
    
    text = (
        f"### 🏃 PLAYER DETAIL — {player['display_name']}\n"
        f"📋 **Position:** {player['position']} | **Age:** {player['age']} years\n"
        f"📈 **Overall:** {player['overall']} OVR | **Potential:** {player['potential']} POT\n\n"
        f"💪 **Fitness:**   {fitness_bar}\n"
        f"🎯 **Sharpness:** {sharpness_bar}\n"
        f"😊 **Morale:**    {morale_bar}\n\n"
        f"🦶 **Preferred Foot:** {player['preferred_foot']}\n"
        f"⭐ **Weak Foot:**      {'★' * player['weak_foot']}{'☆' * (5 - player['weak_foot'])} ({player['weak_foot']}/5)\n"
        f"🔀 **Skill Moves:**    {'★' * player['skill_moves']}{'☆' * (5 - player['skill_moves'])} ({player['skill_moves']}/5)\n"
        f"🧠 **Traits:**         {traits_str}\n\n"
        f"💵 **Market Value:**   {value_str}\n"
        f"📉 **Weekly Wage:**   {wage_str}"
    )
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            back_button("squad", nonce),
            back_button("locker", nonce),
            refresh_button("player", player["id"], nonce),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

def build_player_search_layout(nonce: str) -> V2View:
    """
    Builds a layout prompting the user to search or select from squad.
    """
    text = (
        "### 🏃 Player Search & Details\n"
        "To view a player's detailed stats, you can:\n"
        "1. Open the **Squad Overview** and select a player from the dropdown menu.\n"
        "2. Run the slash command `/player player_name` directly in chat.\n\n"
        "If multiple players match your search query, you will be prompted to select the exact player."
    )
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            back_button("locker", nonce),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

def build_player_match_select_layout(query: str, matches: list[dict], nonce: str) -> V2View:
    """
    Builds a screen when multiple players match a search query.
    """
    text = (
        f"### 🔍 Multiple Players Matched: '{query}'\n"
        "Please select the specific player you wish to view from the dropdown menu below."
    )
    
    options = []
    for p in matches:
        options.append({
            "label": p["display_name"],
            "value": p["id"],
            "description": f"{p['position']} | OVR {p['overall']} | POT {p['potential']}"
        })
        
    select_custom_id = encode_custom_id("player", "view", "select", nonce)
    player_select = select_menu(
        custom_id=select_custom_id,
        options=options,
        placeholder="🔍 Select player...",
        disabled=False
    )
    
    comp_payload = [
        container([
            text_display(text)
        ]),
        action_row([
            player_select
        ]),
        action_row([
            back_button("locker", nonce),
            close_button(nonce)
        ])
    ]
    return V2View(comp_payload)

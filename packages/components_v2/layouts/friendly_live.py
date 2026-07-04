from app.ui.components import (
    container,
    text_display,
    action_row,
    success_button,
    danger_button,
    secondary_button,
    select_menu,
    V2View,
)
from app.ui.custom_ids import encode_custom_id
from app.ui.layouts.common import close_button

def build_friendly_invite_layout(
    challenger_club_name: str,
    opponent_club_name: str,
    opponent_mention: str,
    nonce: str,
    expires_timestamp: int
) -> V2View:
    """
    Builds the components layout for a friendly match challenge invitation card.
    """
    msg = (
        f"### 🤝 **FRIENDLY CHALLENGE**\n"
        f"**{challenger_club_name}** has challenged **{opponent_club_name}** to a friendly match!\n\n"
        f"Manager {opponent_mention}, do you accept this challenge?\n\n"
        f"⏱️ **Expires:** <t:{expires_timestamp}:R>"
    )
    
    accept_id = encode_custom_id("friendly", "accept", "challenge", nonce)
    decline_id = encode_custom_id("friendly", "decline", "challenge", nonce)
    cancel_id = encode_custom_id("friendly", "cancel", "challenge", nonce)
    
    buttons = [
        success_button("⚔️ Accept (Opponent)", accept_id),
        danger_button("❌ Decline (Opponent)", decline_id),
        secondary_button("🗑️ Cancel (Challenger)", cancel_id)
    ]
    
    comp_payload = [
        container([text_display(msg)]),
        action_row(buttons)
    ]
    return V2View(comp_payload)

def build_friendly_practice_layout(nonce: str) -> V2View:
    """
    Builds the Components V2 selection layout for practice matches.
    """
    msg = (
        f"### 🤖 **PRACTICE HUB**\n"
        f"Select a virtual bot difficulty level below to play an instant practice friendly match. "
        f"Practice matches do not affect league standings or player fitness."
    )
    
    options = [
        {"label": "🤖 Beginner Bot FC (50-59 OVR)", "value": "beginner", "description": "Good for testing basic lineups"},
        {"label": "🤖 Amateur United (60-69 OVR)", "value": "amateur", "description": "A light training challenge"},
        {"label": "🤖 Professional City (70-79 OVR)", "value": "professional", "description": "Standard competitive practice"},
        {"label": "🤖 World Class Stars (80-89 OVR)", "value": "world_class", "description": "A tough tactical examination"},
        {"label": "🤖 Legendary Eleven (90-95 OVR)", "value": "legend", "description": "The ultimate test for your starting XI"}
    ]
    
    select_id = encode_custom_id("friendly", "practice", "select", nonce)
    
    comp_payload = [
        container([text_display(msg)]),
        action_row([select_menu(select_id, options, placeholder="Select bot difficulty...")]),
        action_row([close_button(nonce)])
    ]
    return V2View(comp_payload)

def build_live_kickoff_layout(home_name: str, away_name: str, nonce: str) -> V2View:
    """
    Step 1 — Match Starts layout.
    """
    msg = (
        f"### 🤝 **FRIENDLY MATCH STARTED**\n"
        f"**{home_name}** vs **{away_name}**\n\n"
        f"0' 📢 The referee blows the whistle!"
    )
    skip_id = encode_custom_id("friendly", "skip", "match", nonce)
    return V2View([
        container([text_display(msg)]),
        action_row([danger_button("⏭️ Skip to Full-Time", skip_id)])
    ])

def build_live_chunk_layout(
    home_name: str,
    away_name: str,
    home_score: int,
    away_score: int,
    minute: int,
    events_text: str,
    nonce: str
) -> V2View:
    """
    Step 2 — Progressive Live Match Chunk layout.
    """
    header = (
        f"### 🤝 **FRIENDLY MATCH LIVE**\n"
        f"**{home_name}**  {home_score}–{away_score}  **{away_name}**\n\n"
        f"⏳ **{minute}'**"
    )
    skip_id = encode_custom_id("friendly", "skip", "match", nonce)
    return V2View([
        container([text_display(header)]),
        container([text_display(events_text)]),
        action_row([danger_button("⏭️ Skip to Full-Time", skip_id)])
    ])

def build_live_halftime_layout(
    home_name: str,
    away_name: str,
    home_score: int,
    away_score: int,
    events_text: str,
    stats_text: str,
    nonce: str
) -> V2View:
    """
    Step 3 — Half-Time layout.
    """
    header = (
        f"### ⏸️ **HALF-TIME**\n"
        f"**{home_name}**  {home_score}–{away_score}  **{away_name}**\n"
    )
    skip_id = encode_custom_id("friendly", "skip", "match", nonce)
    return V2View([
        container([text_display(header)]),
        container([text_display(events_text)]),
        container([text_display(stats_text)]),
        action_row([danger_button("⏭️ Skip to Full-Time", skip_id)])
    ])

def build_live_fulltime_layout(
    home_name: str,
    away_name: str,
    home_score: int,
    away_score: int,
    motm_name: str,
    events_text: str,
    stats_text: str,
    nonce: str
) -> V2View:
    """
    Step 4 — Full-Time layout.
    """
    if home_score > away_score:
        result_text = f"🏆 **Winner:** **{home_name}**! Congratulations! 🎉"
    elif away_score > home_score:
        result_text = f"🏆 **Winner:** **{away_name}**! Congratulations! 🎉"
    else:
        result_text = f"🤝 **Result:** It's a hard-fought draw! Well played to both clubs!"

    header = (
        f"### 🏁 **FULL-TIME**\n"
        f"**{home_name}**  {home_score}–{away_score}  **{away_name}**\n\n"
        f"🏅 **Man of the Match:** **{motm_name}**\n"
        f"{result_text}"
    )
    return V2View([
        container([text_display(header)]),
        container([text_display(stats_text)]),
        container([text_display(events_text)])
    ])

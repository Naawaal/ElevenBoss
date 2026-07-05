# apps/discord_bot/embeds/squad_embeds.py
from __future__ import annotations
import discord

def get_slot_position(formation: str, slot: int) -> str:
    """Helper to determine the expected position of a slot based on the formation."""
    if slot == 1:
        return "GK"
    try:
        parts = [int(x) for x in formation.split("-")]
        num_def, num_mid, num_fwd = parts[0], parts[1], parts[2]
        if 2 <= slot <= 1 + num_def:
            return "DEF"
        if 1 + num_def < slot <= 1 + num_def + num_mid:
            return "MID"
        return "FWD"
    except Exception:
        # Fallback to general positions
        return "DEF"

def starting_11_embed(formation: str, assignments: dict[int, dict]) -> discord.Embed:
    """Visually stunning starting 11 embed with positional emojis and clean formatting."""
    embed = discord.Embed(
        title=f"📋 Starting 11 (Formation: {formation})",
        description="Your active squad configuration for match simulations.",
        color=0x00FF87  # Premium pitch green
    )

    emoji_map = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
    rarity_emojis = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}

    for slot in range(1, 12):
        req_pos = get_slot_position(formation, slot)
        card = assignments.get(slot)
        
        if card:
            rarity_emoji = rarity_emojis.get(card["rarity"], "⚪")
            role = card.get("role", "Balanced")
            morale = card.get("morale", 80)
            ps_list = card.get("playstyles")
            ps_str = f"\n✨ {', '.join(ps_list)}" if ps_list else ""
            value = f"{rarity_emoji} **{card['name']}**\n**{card['overall']} OVR** | {card['position']}\n💼 {role} | Morale: {morale}%{ps_str}"
        else:
            value = "❌ *[EMPTY]*"
        
        slot_emoji = emoji_map.get(req_pos, "🏃")
        embed.add_field(name=f"{slot_emoji} Slot {slot} ({req_pos})", value=value, inline=True)

    return embed

def roster_embed(cards: list[dict], current_page: int, total_pages: int) -> discord.Embed:
    """Visually stunning roster embed for manager's player collection."""
    embed = discord.Embed(
        title="🗂️ Club Player Roster",
        description=f"Showing page {current_page + 1} of {total_pages} ({len(cards)} total cards)",
        color=0x00FF87
    )
    
    # We display cards on the current page (managed by the RosterPaginationView)
    # The view slices the list, but we can pass the pre-sliced page list here, or slice it inside.
    # To keep this function pure and generic, it accepts the full cards list and slices it.
    per_page = 8
    start = current_page * per_page
    end = start + per_page
    page_cards = cards[start:end]

    rarity_emojis = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}

    for card in page_cards:
        rarity_emoji = rarity_emojis.get(card["rarity"], "⚪")
        details = (
            f"**ID**: `{card['id']}`\n"
            f"**Position**: {card['position']} | **Rarity**: {card['rarity']}\n"
            f"**Overall**: **{card['overall']} OVR** (Level {card['level']})"
        )
        embed.add_field(name=f"{rarity_emoji} {card['name']}", value=details, inline=True)
        
    embed.set_footer(text="Use /squad to configure your starting 11.")
    return embed

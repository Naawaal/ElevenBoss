# apps/discord_bot/embeds/squad_embeds.py
from __future__ import annotations
import discord
from match_engine import get_slot_role
from player_engine import TIER_NAMES, fatigue_indicator


def get_slot_position(formation: str, slot: int) -> str:
    """Helper to determine the expected position of a slot based on the formation."""
    return get_slot_role(formation, slot)

def starting_11_embed(formation: str, assignments: dict[int, dict]) -> discord.Embed:
    """Visually stunning starting 11 embed with positional emojis and clean formatting."""
    embed = discord.Embed(
        title=f"📋 Starting 11 (Formation: {formation})",
        description=(
            "Your active squad configuration for match simulations.\n"
            "Legend: 🟢 rested · 🟡 OK · 🪫 tired · 🔴 exhausted · 🩹 injured"
        ),
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
            fat = int(card.get("fatigue", 100))
            fit = "🩹" if card.get("injury_tier") else fatigue_indicator(fat)
            inj = ""
            if card.get("injury_tier"):
                sev = int(card["injury_tier"])
                inj = f"\n🩹 **{TIER_NAMES.get(sev, 'Injured')}**"
                if card.get("injury_recovery_days") is not None:
                    inj += f" · ~{int(card.get('injury_recovery_days') or 0)}d"
            ps_list = card.get("playstyles")
            ps_str = f"\n✨ {', '.join(ps_list)}" if ps_list else ""
            value = (
                f"{rarity_emoji} **{card['name']}** {fit}\n"
                f"**{card['overall']} OVR** | {card['position']} | Fatigue **{fat}%**\n"
                f"💼 {role} | Morale: {morale}%{inj}{ps_str}"
            )
        else:
            value = "❌ *[EMPTY]*"
        
        slot_emoji = emoji_map.get(req_pos, "🏃")
        embed.add_field(name=f"{slot_emoji} Slot {slot} ({req_pos})", value=value, inline=True)

    return embed

def roster_embed(
    cards: list[dict],
    current_page: int,
    total_pages: int,
    *,
    per_page: int = 8,
) -> discord.Embed:
    """Roster embed with OVR text list for the current page plus grid image."""
    start = current_page * per_page
    page_cards = cards[start : start + per_page]
    rarity_emojis = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}

    embed = discord.Embed(
        title="🗂️ Club Player Roster",
        description=f"Page **{current_page + 1}** of **{total_pages}** · **{len(cards)}** total cards",
        color=0x00FF87,
    )

    if page_cards:
        for card in page_cards:
            ovr = card.get("overall", "?")
            pos = card.get("position", "???")
            name = card.get("name", "Unknown")
            rarity = rarity_emojis.get(card.get("rarity", "Common"), "⚪")
            embed.add_field(
                name=f"{rarity} **{ovr} OVR** · {pos}",
                value=(
                    f"**{name}** · Lvl {card.get('level', 1)} · "
                    f"{'🩹' if card.get('injury_tier') else fatigue_indicator(int(card.get('fatigue', 100)))} "
                    f"{card.get('fatigue', 100)}%"
                ),
                inline=True,
            )
    else:
        embed.description += "\n\n_No players on this page._"

    embed.set_image(url="attachment://roster_grid.png")
    embed.set_footer(text="Use /squad to configure your starting 11.")
    return embed

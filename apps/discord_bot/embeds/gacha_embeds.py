# apps/discord_bot/embeds/gacha_embeds.py
from __future__ import annotations
import discord
from gacha import GachaPlayer, GachaPack

def gacha_claim_embed(pack: GachaPack) -> discord.Embed:
    """Beautiful embed showing the 5 claimed gacha cards."""
    embed = discord.Embed(
        title="🎉 Free Daily Pack Claimed!",
        description="Here are the 5 players who have joined your academy roster:",
        color=0x00FF87
    )
    
    for i, player in enumerate(pack.players, 1):
        rarity_emoji = {
            "Common": "⚪",
            "Rare": "🔵",
            "Epic": "🟣",
            "Legendary": "🟡"
        }.get(player.rarity, "⚪")
        
        details = (
            f"**Position**: {player.position}\n"
            f"**Age**: {player.age} yrs\n"
            f"**Rarity**: {player.rarity}\n"
            f"**Rating**: **{player.overall} OVR** · 📊 {player.potential} POT"
        )
        embed.add_field(
            name=f"{i}. {rarity_emoji} {player.name}",
            value=details,
            inline=False
        )
    
    embed.set_footer(text="Manage your squad using /squad view")
    return embed

def gacha_cooldown_embed(remaining_seconds: float) -> discord.Embed:
    """Embed showing remaining cooldown for gacha claim."""
    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    seconds = int(remaining_seconds % 60)
    
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    embed = discord.Embed(
        title="⏳ Gacha Pack Cooldown",
        description=(
            f"Your daily player pack is not ready yet.\n\n"
            f"You can claim another free pack in **{time_str}**."
        ),
        color=0xE74C3C
    )
    embed.set_footer(text="Pack refreshes every 22 hours.")
    return embed

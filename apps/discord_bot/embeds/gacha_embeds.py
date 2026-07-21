# apps/discord_bot/embeds/gacha_embeds.py
from __future__ import annotations
import discord
from gacha import GachaPack

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
            f"**Role**: {player.role}\n"
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
    embed.set_footer(text="Pack refreshes every 12 hours (requires a new Top.gg vote).")
    return embed


def topgg_vote_prompt_embed(vote_url: str) -> discord.Embed:
    embed = discord.Embed(
        title="🗳️ Vote Required",
        description=(
            "To claim your free pack, vote for ElevenBoss on Top.gg first.\n\n"
            "1. Click the link below to vote\n"
            "2. Return here and click **Vote & Claim Free Pack** again\n\n"
            f"Vote link: {vote_url}"
        ),
        color=0xFFAA00,
    )
    embed.set_footer(text="Votes reset every 12 hours on Top.gg.")
    return embed


def topgg_vote_unavailable_embed() -> discord.Embed:
    return discord.Embed(
        title="⚠️ Vote Verification Unavailable",
        description=(
            "We couldn't verify your Top.gg vote right now. Please try again in a few minutes.\n\n"
            "Your pack was **not** claimed."
        ),
        color=0xE74C3C,
    )


def topgg_vote_replay_embed() -> discord.Embed:
    return discord.Embed(
        title="🗳️ Vote Already Used",
        description=(
            "This Top.gg vote was already used for a free pack. "
            "Vote again after your cooldown to claim another pack."
        ),
        color=0xFFAA00,
    )

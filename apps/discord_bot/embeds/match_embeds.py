# apps/discord_bot/embeds/match_embeds.py
from __future__ import annotations
import discord
from match_engine import MatchResult

def match_result_embed(result: MatchResult, club_name: str, opponent_name: str) -> discord.Embed:
    """Rich embed to display match simulation outcomes."""
    colors = {
        "win": 0x2ECC71,   # Green
        "draw": 0xF1C40F,  # Yellow
        "loss": 0xE74C3C   # Red
    }
    color = colors.get(result.result, 0x7F8C8D)
    
    emoji = {
        "win": "🎉 WIN",
        "draw": "🤝 DRAW",
        "loss": "💔 LOSS"
    }.get(result.result, "⚽ MATCH")

    embed = discord.Embed(
        title=f"{emoji}: {club_name} vs {opponent_name}",
        color=color
    )
    
    embed.add_field(
        name="🥅 Full-Time Score",
        value=f"## **{result.goals_for} - {result.goals_against}**",
        inline=False
    )
    
    embed.add_field(name="🛡️ Your Rating", value=f"{result.my_rating} OVR", inline=True)
    embed.add_field(name="🤖 Opponent Rating", value=f"{result.opponent_rating} OVR", inline=True)
    
    rewards = []
    if result.coins_earned > 0:
        rewards.append(f"🪙 **+{result.coins_earned} coins**")
    if result.points_earned > 0:
        rewards.append(f"🏆 **+{result.points_earned} league pts**")
    
    rewards_str = ", ".join(rewards) if rewards else "No rewards earned."
    embed.add_field(name="🎁 Match Rewards", value=rewards_str, inline=False)
    
    embed.set_footer(text="ElevenBoss League Match Simulation")
    return embed

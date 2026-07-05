# apps/discord_bot/middleware/guard.py
from __future__ import annotations
import discord
from discord import app_commands
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed

async def ensure_registered(interaction: discord.Interaction) -> bool:
    """
    Checks if the user has a registered club.
    If not, responds with an ephemeral error prompting them to use /register.
    Does NOT write any database rows.
    """
    db = await get_client()
    try:
        result = await db.table("players").select("discord_id") \
            .eq("discord_id", interaction.user.id).maybe_single().execute()
        
        if result is None or result.data is None:
            await interaction.response.send_message(
                embed=error_embed("You don't have a club yet! Run `/register` to get started."),
                ephemeral=True
            )
            return False
        return True
    except Exception as e:
        # Fallback error handling in case db query fails
        await interaction.response.send_message(
            embed=error_embed(f"Database error during registration check: {str(e)}"),
            ephemeral=True
        )
        return False

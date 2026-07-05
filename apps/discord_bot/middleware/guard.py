# apps/discord_bot/middleware/guard.py
from __future__ import annotations
import discord
from discord import app_commands
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed

async def ensure_registered(interaction: discord.Interaction) -> bool:
    """
    Checks if the user has a registered club.
    Defers the interaction immediately to prevent 3-second API timeouts.
    """
    is_public = False
    if interaction.command:
        # Check if it is the /battle bot subcommand
        if interaction.command.name == "bot" and interaction.command.parent and interaction.command.parent.name == "battle":
            is_public = True

    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=not is_public)

    db = await get_client()
    try:
        result = await db.table("players").select("discord_id") \
            .eq("discord_id", interaction.user.id).maybe_single().execute()
        
        if result is None or result.data is None:
            await interaction.followup.send(
                embed=error_embed("You don't have a club yet! Run `/register` to get started."),
                ephemeral=True
            )
            return False
        return True
    except Exception as e:
        await interaction.followup.send(
            embed=error_embed(f"Database error during registration check: {str(e)}"),
            ephemeral=True
        )
        return False

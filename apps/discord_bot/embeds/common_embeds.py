# apps/discord_bot/embeds/common_embeds.py
from __future__ import annotations
import discord

def error_embed(message: str) -> discord.Embed:
    """Standardized error embed."""
    return discord.Embed(
        title="❌ Error",
        description=message,
        color=0xFF3333
    )

def success_embed(message: str) -> discord.Embed:
    """Standardized success embed."""
    return discord.Embed(
        title="✅ Success",
        description=message,
        color=0x00FF87
    )

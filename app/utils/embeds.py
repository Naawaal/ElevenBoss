import discord
from typing import Optional, List

# Standard design colors for a polished look (avoiding generic red/green/blue)
COLOR_INFO = 0x3B82F6      # Sleek Blue (Tailwind Blue-500)
COLOR_SUCCESS = 0x10B981   # Emerald Green (Tailwind Emerald-500)
COLOR_WARNING = 0xF59E0B   # Amber/Gold (Tailwind Amber-500)
COLOR_ERROR = 0xEF4444     # Rose Red (Tailwind Rose-500)

def info_embed(
    title: str, 
    description: str, 
    fields: Optional[List[dict]] = None
) -> discord.Embed:
    """Creates a standard information embed."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLOR_INFO
    )
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", True)
            )
    return embed

def success_embed(title: str, description: str) -> discord.Embed:
    """Creates a standard success confirmation embed."""
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=COLOR_SUCCESS
    )

def warning_embed(title: str, description: str) -> discord.Embed:
    """Creates a standard warning embed."""
    return discord.Embed(
        title=f"⚠️ {title}",
        description=description,
        color=COLOR_WARNING
    )

def error_embed(title: str, description: str) -> discord.Embed:
    """Creates a standard error/failure embed."""
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=COLOR_ERROR
    )

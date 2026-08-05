# apps/discord_bot/embeds/changelog_embeds.py
"""Changelog announcement embed builder (Feature 055)."""
from __future__ import annotations

from typing import TYPE_CHECKING
import discord

if TYPE_CHECKING:
    from apps.discord_bot.core.deployment_changelog import ChangelogEntry


def build_changelog_embed(entry: ChangelogEntry, commit_hash: str) -> discord.Embed:
    short_commit = commit_hash[:7] if commit_hash else "unknown"
    title = f"🚀 ElevenBoss {entry.version} is live"

    embed = discord.Embed(
        title=title,
        description="A new deployment has arrived.",
        color=0x2ECC71,  # Green
    )

    icon_map = {
        "Added": "✨ Added",
        "Changed": "🔄 Changed",
        "Fixed": "🛠️ Fixed",
        "Removed": "🗑️ Removed",
    }

    # Render sections (max 4 sections, max 6 items per section)
    sections_rendered = 0
    for section_name, items in entry.sections.items():
        if not items or sections_rendered >= 4:
            continue
        field_name = icon_map.get(section_name, f"• {section_name}")
        lines = []
        for item in items[:6]:
            clean_item = item.strip()
            if clean_item.startswith("- "):
                clean_item = clean_item[2:]
            if len(clean_item) > 180:
                clean_item = clean_item[:177] + "..."
            lines.append(f"• {clean_item}")

        if lines:
            embed.add_field(name=field_name, value="\n".join(lines), inline=False)
            sections_rendered += 1

    embed.set_footer(text=f"Deployed from {short_commit}")
    return embed

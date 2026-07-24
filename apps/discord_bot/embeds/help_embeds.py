# apps/discord_bot/embeds/help_embeds.py
"""Embed builders for /help hub and topics."""
from __future__ import annotations

import discord

from apps.discord_bot.core.help_catalog import (
    DOCS_BASE,
    HelpTopic,
    list_topics,
    resolve_docs_url,
)

HELP_COLOR = 0x00FF87


def build_help_hub_embed(
    *,
    emphasize_getting_started: bool = False,
    notice: str | None = None,
) -> discord.Embed:
    description_parts: list[str] = [
        "Your in-Discord guide to ElevenBoss systems and commands.",
        "Tap a category below, or use `/help topic:` for a shortcut.",
    ]
    if emphasize_getting_started:
        description_parts.insert(
            0,
            "**New here?** Start with **Getting Started**, then run **`/register`**.",
        )
    if notice:
        description_parts.append(f"\n⚠️ {notice}")

    embed = discord.Embed(
        title="📖 ElevenBoss Help",
        description="\n".join(description_parts),
        color=HELP_COLOR,
    )
    for topic in list_topics():
        embed.add_field(
            name=f"{topic.emoji} {topic.label}",
            value=topic.hub_blurb,
            inline=True,
        )
    embed.set_footer(text=f"Full docs · {DOCS_BASE}")
    return embed


def build_help_topic_embed(
    topic: HelpTopic,
    *,
    command_blocks: list[str] | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=topic.title,
        description=None,
        color=HELP_COLOR,
    )

    if topic.is_commands:
        blocks = command_blocks or [
            "Commands unavailable — try again after the bot finishes syncing."
        ]
        for i, block in enumerate(blocks):
            name = "Slash commands" if i == 0 else f"Slash commands (cont. {i + 1})"
            embed.add_field(name=name, value=block, inline=False)
    else:
        for field in topic.fields:
            embed.add_field(name=field.name, value=field.value, inline=False)

    docs_url = resolve_docs_url(topic.docs_path)
    embed.set_footer(text=f"Read more · {docs_url}")
    return embed

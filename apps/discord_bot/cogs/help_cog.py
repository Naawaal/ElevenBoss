# apps/discord_bot/cogs/help_cog.py
"""ElevenBoss /help — in-Discord documentation hub (046)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.core.help_catalog import (
    get_topic,
    list_topics,
    topic_choices_for_autocomplete,
)
from apps.discord_bot.core.help_commands import (
    chunk_text_blocks,
    format_command_lines,
    harvest_command_entries,
)
from apps.discord_bot.core.view_helpers import safe_defer
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.help_embeds import build_help_hub_embed, build_help_topic_embed
from apps.discord_bot.views.help_hub import HelpHubView, HelpTopicView

logger = logging.getLogger(__name__)


async def _club_exists(user_id: int) -> bool | None:
    """True if registered, False if not, None if lookup failed (fail-open)."""
    try:
        db = await get_client()
        res = (
            await db.table("players")
            .select("discord_id")
            .eq("discord_id", user_id)
            .maybe_single()
            .execute()
        )
        return bool(res and res.data)
    except Exception:
        logger.warning("Help club check failed for %s (fail-open)", user_id, exc_info=True)
        return None


async def topic_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=name, value=value)
        for name, value in topic_choices_for_autocomplete(current)
    ]


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Open the ElevenBoss in-Discord guide (systems, hubs, and commands).",
    )
    @app_commands.describe(topic="Jump straight to a help category")
    @app_commands.autocomplete(topic=topic_autocomplete)
    async def help_command(
        self,
        interaction: discord.Interaction,
        topic: str | None = None,
    ) -> None:
        ephemeral = interaction.guild_id is not None
        if not await safe_defer(interaction, ephemeral=ephemeral):
            return

        club = await _club_exists(interaction.user.id)
        emphasize = club is False

        notice: str | None = None
        resolved = None
        if topic and topic.strip():
            resolved = get_topic(topic.strip())
            if resolved is None:
                valid = ", ".join(t.id for t in list_topics())
                notice = f"Unknown topic `{topic.strip()}`. Showing the hub. Try: {valid}"

        if resolved is not None:
            command_blocks = None
            if resolved.is_commands:
                entries = harvest_command_entries(interaction.client.tree)
                command_blocks = chunk_text_blocks(format_command_lines(entries))
            embed = build_help_topic_embed(resolved, command_blocks=command_blocks)
            view = HelpTopicView(
                interaction.user.id,
                resolved.id,
                emphasize_getting_started=emphasize,
            )
        else:
            embed = build_help_hub_embed(
                emphasize_getting_started=emphasize,
                notice=notice,
            )
            view = HelpHubView(
                interaction.user.id,
                emphasize_getting_started=emphasize,
            )

        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))

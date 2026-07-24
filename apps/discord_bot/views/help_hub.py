# apps/discord_bot/views/help_hub.py
"""Interactive /help hub and topic navigation views."""
from __future__ import annotations

import logging

import discord

from apps.discord_bot.core.help_catalog import (
    DOCS_BASE,
    get_topic,
    list_topics,
    resolve_docs_url,
)
from apps.discord_bot.core.help_commands import (
    chunk_text_blocks,
    format_command_lines,
    harvest_command_entries,
)
from apps.discord_bot.core.view_helpers import disable_view_on_timeout
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.embeds.help_embeds import build_help_hub_embed, build_help_topic_embed

logger = logging.getLogger(__name__)

_STALE_HINT = "This help menu expired. Run `/help` again."
_NOT_YOURS = "This help menu belongs to another manager."


def _button_label(emoji: str, label: str) -> str:
    # Discord button label max 80
    text = f"{emoji} {label}"
    return text[:80]


def _command_blocks_for(interaction: discord.Interaction) -> list[str]:
    tree = getattr(interaction.client, "tree", None)
    entries = harvest_command_entries(tree)
    return chunk_text_blocks(format_command_lines(entries))


class HelpHubView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        *,
        emphasize_getting_started: bool = False,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.emphasize_getting_started = emphasize_getting_started

        for index, topic in enumerate(list_topics()):
            row = min(index // 5, 3)
            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=_button_label(topic.emoji, topic.label),
                custom_id=f"help_hub:{topic.id}",
                row=row,
            )
            button.callback = self._topic_callback(topic.id)
            self.add_item(button)

        docs_row = 2 if len(list_topics()) <= 10 else 4
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="📚 Full Documentation",
                url=DOCS_BASE,
                row=docs_row,
            )
        )

    def _topic_callback(self, topic_id: str):
        async def _callback(interaction: discord.Interaction) -> None:
            await self.show_topic(interaction, topic_id)

        return _callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(_NOT_YOURS, ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        logger.exception("Help hub view error: %s", error)
        try:
            msg = error_embed(_STALE_HINT)
            if interaction.response.is_done():
                await interaction.followup.send(embed=msg, ephemeral=True)
            else:
                await interaction.response.send_message(embed=msg, ephemeral=True)
        except discord.HTTPException:
            pass

    async def show_topic(self, interaction: discord.Interaction, topic_id: str) -> None:
        topic = get_topic(topic_id)
        if topic is None:
            await interaction.response.send_message(
                embed=error_embed("Unknown help topic. Run `/help` again."),
                ephemeral=True,
            )
            return

        command_blocks = _command_blocks_for(interaction) if topic.is_commands else None
        embed = build_help_topic_embed(topic, command_blocks=command_blocks)
        view = HelpTopicView(
            self.owner_id,
            topic.id,
            emphasize_getting_started=self.emphasize_getting_started,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class HelpTopicView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        topic_id: str,
        *,
        emphasize_getting_started: bool = False,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.topic_id = topic_id
        self.emphasize_getting_started = emphasize_getting_started

        topic = get_topic(topic_id)
        docs_url = resolve_docs_url(topic.docs_path if topic else None)

        back = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="⬅️ Back",
            custom_id="help_back",
            row=0,
        )
        back.callback = self._back
        self.add_item(back)

        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="📖 Read More",
                url=docs_url,
                row=0,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(_NOT_YOURS, ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        logger.exception("Help topic view error: %s", error)
        try:
            msg = error_embed(_STALE_HINT)
            if interaction.response.is_done():
                await interaction.followup.send(embed=msg, ephemeral=True)
            else:
                await interaction.response.send_message(embed=msg, ephemeral=True)
        except discord.HTTPException:
            pass

    async def _back(self, interaction: discord.Interaction) -> None:
        embed = build_help_hub_embed(
            emphasize_getting_started=self.emphasize_getting_started,
        )
        view = HelpHubView(
            self.owner_id,
            emphasize_getting_started=self.emphasize_getting_started,
        )
        await interaction.response.edit_message(embed=embed, view=view)

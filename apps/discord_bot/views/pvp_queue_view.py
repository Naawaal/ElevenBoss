# apps/discord_bot/views/pvp_queue_view.py
"""Ranked PvP queue interactions (Feature 053)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord

from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.pvp_embeds import queue_timeout_embed, searching_embed
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

if TYPE_CHECKING:
    from apps.discord_bot.cogs.battle_cog import BattleCog

logger = logging.getLogger(__name__)


class PvpQueueView(discord.ui.View):
    def __init__(
        self,
        cog: BattleCog,
        owner_id: int,
        queue_payload: dict[str, Any],
        *,
        timed_out: bool = False,
    ) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id
        self.queue_payload = queue_payload
        self.timed_out = timed_out
        if timed_out:
            self.clear_items()
            self.add_item(ContinueSearchButton())
            self.add_item(AiPracticeFallbackButton())
            self.add_item(CancelSearchButton())
        else:
            self.clear_items()
            self.add_item(CancelSearchButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This search belongs to another manager.", ephemeral=True)
            return False
        return True


class CancelSearchButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label="Cancel Search", custom_id="pvp_cancel_search")

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PvpQueueView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        db = await get_client()
        qid = view.queue_payload.get("queue_id")
        try:
            await db.rpc(
                "cancel_pvp_queue",
                {"p_owner_id": interaction.user.id, "p_queue_id": qid},
            ).execute()
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)
            return
        await interaction.followup.send(embed=success_embed("Search cancelled. No energy was spent."), ephemeral=True)
        self.view.stop()


class ContinueSearchButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(style=discord.ButtonStyle.primary, label="Continue Search", custom_id="pvp_continue_search")

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PvpQueueView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        await view.cog.start_pvp_search(interaction)


class AiPracticeFallbackButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(style=discord.ButtonStyle.danger, label="AI Practice", custom_id="pvp_timeout_practice")

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PvpQueueView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        # Cancel leftover queue if any, then Practice (US3 wires Practice path)
        db = await get_client()
        try:
            await db.rpc(
                "cancel_pvp_queue",
                {"p_owner_id": interaction.user.id, "p_queue_id": view.queue_payload.get("queue_id")},
            ).execute()
        except Exception:
            logger.debug("cancel before practice fallback ignored", exc_info=True)
        await view.cog.execute_bot_battle(interaction)


def parse_joined_at(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


async def build_search_followup(
    interaction: discord.Interaction,
    cog: BattleCog,
    payload: dict[str, Any],
    *,
    timed_out: bool = False,
) -> None:
    if timed_out:
        embed = queue_timeout_embed()
        view = PvpQueueView(cog, interaction.user.id, payload, timed_out=True)
    else:
        embed = searching_embed(
            division=str(payload.get("global_division", "?")),
            global_lp=int(payload.get("global_lp") or 0),
            xi_rating=float(payload.get("xi_rating") or 0),
            joined_at=parse_joined_at(payload["joined_at"]),
        )
        view = PvpQueueView(cog, interaction.user.id, payload, timed_out=False)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

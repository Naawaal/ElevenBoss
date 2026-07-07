# apps/discord_bot/views/level_reward_claim.py
from __future__ import annotations

import logging

import discord

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)


async def unclaimed_reward_count(owner_id: int) -> int:
    db = await get_client()
    res = await db.rpc(
        "count_unclaimed_level_rewards",
        {"p_owner_id": owner_id},
    ).execute()
    return int(res.data or 0)


async def claim_level_rewards(owner_id: int) -> tuple[int, int]:
    """Claim pending rewards. Returns (players_claimed, total_points)."""
    db = await get_client()
    res = await db.rpc("claim_pending_level_rewards", {
        "p_owner_id": owner_id,
    }).execute()
    data = res.data or {}
    return int(data.get("players_claimed", 0)), int(data.get("total_points", 0))


class ClaimAllLevelRewardsView(discord.ui.View):
    """Persistent view — owner resolved from interaction.user.id at click time."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        style=discord.ButtonStyle.success,
        label="🎁 Claim All",
        custom_id="claim_level_rewards_all",
    )
    async def claim_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        owner_id = interaction.user.id
        try:
            if await unclaimed_reward_count(owner_id) <= 0:
                await interaction.followup.send(
                    embed=error_embed("No unclaimed level rewards found for your club."),
                    ephemeral=True,
                )
                return

            claimed, total = await claim_level_rewards(owner_id)
            if claimed <= 0:
                await interaction.followup.send(
                    embed=error_embed("No rewards could be claimed. They may already be claimed."),
                    ephemeral=True,
                )
                return

            for child in self.children:
                child.disabled = True

            if interaction.message:
                embed = interaction.message.embeds[0] if interaction.message.embeds else None
                if embed:
                    embed.color = 0x00FF87
                    embed.title = "✅ Level-Up Rewards Claimed!"
                    embed.description = (
                        f"You claimed **{total}** skill points across **{claimed}** player(s).\n\n"
                        "Open `/development` → **Allocate Skills** to spend them."
                    )
                    await interaction.message.edit(embed=embed, view=self)

            await interaction.followup.send(
                embed=success_embed(
                    f"Claimed **{total}** skill points for **{claimed}** player(s). "
                    "Use `/development` → Allocate Skills to spend them."
                ),
                ephemeral=True,
            )
        except Exception as exc:
            logger.exception("Failed claiming level rewards.")
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

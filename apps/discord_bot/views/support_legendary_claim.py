# apps/discord_bot/views/support_legendary_claim.py
"""One-shot Legendary thank-you claim (DM persistent view + hub helpers)."""
from __future__ import annotations

import logging

import discord

from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.core.card_payload import card_rpc_payload
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from gacha import generate_support_legendary

logger = logging.getLogger(__name__)


async def support_legendary_enabled(db) -> bool:
    try:
        res = await db.rpc("support_legendary_reward_enabled").execute()
        return bool(res.data)
    except Exception:
        logger.exception("support_legendary_reward_enabled RPC failed")
        return False


async def support_legendary_pending(owner_id: int) -> bool:
    db = await get_client()
    if not await support_legendary_enabled(db):
        return False
    try:
        res = await db.rpc(
            "support_legendary_reward_pending",
            {"p_owner_id": owner_id},
        ).execute()
        return bool(res.data)
    except Exception:
        logger.exception("support_legendary_reward_pending failed for %s", owner_id)
        return False


async def ensure_pending_legendary(owner_id: int) -> dict | None:
    """Generate+store pending card once; return pending_card dict or None if ineligible."""
    db = await get_client()
    if not await support_legendary_enabled(db):
        return None

    row_res = (
        await db.table("support_legendary_rewards")
        .select("claimed, pending_card")
        .eq("discord_id", owner_id)
        .maybe_single()
        .execute()
    )
    row = row_res.data if row_res else None
    if not row or row.get("claimed"):
        return None
    if row.get("pending_card"):
        return row["pending_card"]

    player = generate_support_legendary()
    payload = card_rpc_payload(player)
    res = await db.rpc(
        "prepare_support_legendary_reward",
        {"p_owner_id": owner_id, "p_card": payload},
    ).execute()
    data = res.data or {}
    return data.get("pending_card") or payload


async def claim_support_legendary(owner_id: int) -> dict:
    db = await get_client()
    # Ensure card exists before claim (hub path may claim without prior DM)
    await ensure_pending_legendary(owner_id)
    res = await db.rpc(
        "claim_support_legendary_reward",
        {"p_owner_id": owner_id},
    ).execute()
    return res.data or {}


def legendary_gift_embed(card: dict) -> discord.Embed:
    name = card.get("name", "Unknown")
    position = card.get("position", "?")
    overall = card.get("overall", "?")
    potential = card.get("potential", "?")
    role = card.get("role") or "Balanced"
    embed = discord.Embed(
        title="🎁 Legendary Thank-You Gift!",
        description=(
            "Thanks for supporting ElevenBoss — you've unlocked a **Legendary** player "
            "for the Recover update.\n\n"
            f"**{name}** · `{position}` · **{overall} OVR** · POT **{potential}**\n"
            f"Role: *{role}*\n\n"
            "Click **Claim** below to add them to your club. "
            "If this DM doesn't work, use `/development` → **Claim Legendary Gift**."
        ),
        color=0xFFD700,
    )
    embed.set_footer(text="One-time gift · Legendary · POT 90–95")
    return embed


class ClaimSupportLegendaryView(discord.ui.View):
    """Persistent DM view — owner resolved from interaction.user.id."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        style=discord.ButtonStyle.success,
        label="🎁 Claim",
        custom_id="claim_support_legendary",
    )
    async def claim_btn(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        owner_id = interaction.user.id
        try:
            if not await support_legendary_pending(owner_id):
                await interaction.followup.send(
                    embed=error_embed(
                        "No Legendary gift waiting — it may already be claimed, "
                        "or you're not on the thank-you list."
                    ),
                    ephemeral=True,
                )
                return

            result = await claim_support_legendary(owner_id)
            name = result.get("name", "Your player")
            position = result.get("position", "?")
            overall = result.get("overall", "?")
            potential = result.get("potential", "?")

            for child in self.children:
                child.disabled = True

            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                embed.color = 0x00FF87
                embed.title = "✅ Legendary Gift Claimed!"
                embed.description = (
                    f"**{name}** (`{position}`) is now on your club — "
                    f"**{overall} OVR** / POT **{potential}**.\n\n"
                    "Find them in `/squad` or `/player-profile`."
                )
                await interaction.message.edit(embed=embed, view=self)

            logger.info(
                "Support legendary claimed by %s → %s (%s OVR / POT %s)",
                owner_id,
                name,
                overall,
                potential,
            )
            await interaction.followup.send(
                embed=success_embed(
                    f"Claimed **{name}** (`{position}`) — "
                    f"**{overall} OVR** / POT **{potential}**!"
                ),
                ephemeral=True,
            )
        except Exception as exc:
            logger.exception("Failed claiming support legendary for %s", owner_id)
            await interaction.followup.send(
                embed=error_embed(api_error_message(exc)),
                ephemeral=True,
            )

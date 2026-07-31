# apps/discord_bot/views/manager_card_gift_claim.py
"""One-time manager card gift claim (DM persistent view + hub helpers)."""
from __future__ import annotations

import logging

import discord

from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.core.card_payload import card_rpc_payload
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from gacha import (
    MANAGER_CARD_GIFTS_CAMPAIGN,
    generate_manager_gift_epic,
    generate_manager_gift_legendary_mid,
)

logger = logging.getLogger(__name__)

CAMPAIGN_ID = MANAGER_CARD_GIFTS_CAMPAIGN


async def manager_card_gifts_enabled(db) -> bool:
    try:
        res = await db.rpc("manager_card_gifts_enabled").execute()
        return bool(res.data)
    except Exception:
        logger.exception("manager_card_gifts_enabled RPC failed")
        return False


async def manager_card_gifts_pending_count(owner_id: int) -> int:
    db = await get_client()
    if not await manager_card_gifts_enabled(db):
        return 0
    try:
        res = await db.rpc(
            "manager_card_gifts_pending",
            {"p_owner_id": owner_id},
        ).execute()
        return int(res.data or 0)
    except Exception:
        logger.exception("manager_card_gifts_pending failed for %s", owner_id)
        return 0


def _generate_for_slot(owner_id: int, gift_slot: str):
    if gift_slot == "legendary_mid":
        return generate_manager_gift_legendary_mid(owner_id=owner_id)
    return generate_manager_gift_epic(owner_id=owner_id)


async def ensure_pending_manager_gifts(owner_id: int) -> list[dict]:
    """Prepare all unclaimed gift slots once; return list of {gift_slot, card}."""
    db = await get_client()
    if not await manager_card_gifts_enabled(db):
        return []

    rows_res = (
        await db.table("manager_card_gifts")
        .select("gift_slot, claimed, pending_card")
        .eq("campaign_id", CAMPAIGN_ID)
        .eq("discord_id", owner_id)
        .eq("claimed", False)
        .execute()
    )
    rows = rows_res.data or []
    if not rows:
        return []

    payload_items: list[dict] = []
    prepared: list[dict] = []
    for row in rows:
        slot = row["gift_slot"]
        if row.get("pending_card"):
            prepared.append({"gift_slot": slot, "card": row["pending_card"]})
            continue
        player = _generate_for_slot(owner_id, slot)
        card = card_rpc_payload(player)
        payload_items.append({"gift_slot": slot, "card": card})
        prepared.append({"gift_slot": slot, "card": card})

    if payload_items:
        res = await db.rpc(
            "prepare_manager_card_gifts",
            {"p_owner_id": owner_id, "p_gifts": payload_items},
        ).execute()
        data = res.data or {}
        gifts = data.get("gifts") or []
        if gifts:
            return [
                {"gift_slot": g.get("gift_slot"), "card": g.get("card")}
                for g in gifts
                if g.get("card")
            ]

    return prepared


async def claim_manager_card_gifts(owner_id: int) -> dict:
    db = await get_client()
    await ensure_pending_manager_gifts(owner_id)
    res = await db.rpc(
        "claim_manager_card_gifts",
        {"p_owner_id": owner_id},
    ).execute()
    return res.data or {}


async def set_manager_gift_dm_status(owner_id: int, status: str) -> None:
    db = await get_client()
    await db.rpc(
        "set_manager_card_gift_dm_status",
        {"p_owner_id": owner_id, "p_status": status},
    ).execute()


def manager_gift_embed(gifts: list[dict]) -> discord.Embed:
    lines: list[str] = []
    has_legend = False
    for item in gifts:
        card = item.get("card") or {}
        slot = item.get("gift_slot") or "epic"
        if slot == "legendary_mid":
            has_legend = True
        lines.append(
            f"• **{card.get('name', 'Unknown')}** · `{card.get('position', '?')}` · "
            f"**{card.get('overall', '?')} OVR** / POT **{card.get('potential', '?')}** "
            f"({card.get('rarity', 'Epic')})"
        )

    title = "🎁 Manager Card Gift!" if len(gifts) == 1 else "🎁 Manager Card Gifts!"
    extra = (
        "\n\nOne of these is your special **Legendary MID** boost."
        if has_legend
        else ""
    )
    embed = discord.Embed(
        title=title,
        description=(
            "Thanks for managing in ElevenBoss — you've unlocked "
            f"**{len(gifts)}** free player card(s).\n\n"
            + "\n".join(lines)
            + extra
            + "\n\nClick **Claim** below to add them to your club. "
            "If DMs are blocked, use `/development` → **Claim Card Gift(s)**."
        ),
        color=0x9B59B6,
    )
    embed.set_footer(text="One-time gift · assign via /squad · not auto-added to XI")
    return embed


def _format_claimed_cards(cards: list[dict]) -> str:
    parts = []
    for c in cards:
        parts.append(
            f"**{c.get('name', 'Player')}** (`{c.get('position', '?')}`) — "
            f"**{c.get('overall', '?')} OVR** / POT **{c.get('potential', '?')}**"
        )
    return "\n".join(parts)


class ClaimManagerCardGiftView(discord.ui.View):
    """Persistent DM view — owner resolved from interaction.user.id."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        style=discord.ButtonStyle.success,
        label="🎁 Claim",
        custom_id="claim_manager_card_gifts",
    )
    async def claim_btn(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        owner_id = interaction.user.id
        try:
            pending = await manager_card_gifts_pending_count(owner_id)
            if pending <= 0:
                await interaction.followup.send(
                    embed=error_embed(
                        "No card gift waiting — it may already be claimed, "
                        "or you're not on this campaign list."
                    ),
                    ephemeral=True,
                )
                return

            result = await claim_manager_card_gifts(owner_id)
            cards = result.get("cards") or []
            body = _format_claimed_cards(cards) or "Your gift cards are on your club."

            for child in self.children:
                child.disabled = True

            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                embed.color = 0x00FF87
                embed.title = "✅ Card Gift Claimed!"
                embed.description = (
                    f"{body}\n\nFind them in `/squad` or `/player-profile` "
                    "(not auto-assigned to your Starting XI)."
                )
                await interaction.message.edit(embed=embed, view=self)

            logger.info(
                "Manager card gifts claimed by %s → %s card(s)",
                owner_id,
                len(cards),
            )
            await interaction.followup.send(
                embed=success_embed(f"Claimed:\n{body}"),
                ephemeral=True,
            )
        except Exception as exc:
            logger.exception("Failed claiming manager card gifts for %s", owner_id)
            await interaction.followup.send(
                embed=error_embed(api_error_message(exc)),
                ephemeral=True,
            )

# apps/discord_bot/tasks/support_legendary_notifier.py
"""Startup DMs for unclaimed support Legendary thank-you gifts."""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.views.support_legendary_claim import (
    ClaimSupportLegendaryView,
    ensure_pending_legendary,
    legendary_gift_embed,
    support_legendary_enabled,
)

logger = logging.getLogger(__name__)


async def notify_support_legendary_rewards(bot: commands.Bot) -> None:
    """DM eligible supporters once (idempotent via notified flag)."""
    db = await get_client()
    if not await support_legendary_enabled(db):
        logger.info("Support legendary reward flag off — skip notify.")
        return

    pending_res = (
        await db.table("support_legendary_rewards")
        .select("discord_id")
        .eq("claimed", False)
        .eq("notified", False)
        .execute()
    )
    rows = pending_res.data or []
    if not rows:
        logger.info("No support legendary rewards to notify.")
        return

    for row in rows:
        owner_id = int(row["discord_id"])
        try:
            # Only DM registered clubs (prepare RPC also enforces this)
            club = (
                await db.table("players")
                .select("discord_id")
                .eq("discord_id", owner_id)
                .maybe_single()
                .execute()
            )
            if not club or not club.data:
                logger.info(
                    "Support legendary skip DM for %s — no club yet (hub claim later).",
                    owner_id,
                )
                continue

            card = await ensure_pending_legendary(owner_id)
            if not card:
                continue

            user = await bot.fetch_user(owner_id)
            if user is None:
                continue

            embed = legendary_gift_embed(card)
            await user.send(embed=embed, view=ClaimSupportLegendaryView())

            await (
                db.table("support_legendary_rewards")
                .update({"notified": True})
                .eq("discord_id", owner_id)
                .eq("claimed", False)
                .execute()
            )
            logger.info(
                "Sent support legendary DM to %s (%s).",
                owner_id,
                card.get("name"),
            )
        except discord.Forbidden:
            logger.warning(
                "DM blocked for support legendary owner %s — claim via /development.",
                owner_id,
            )
        except Exception:
            logger.exception("Failed notifying support legendary owner %s.", owner_id)

# apps/discord_bot/tasks/manager_card_gift_notifier.py
"""Startup DMs for unclaimed one-time manager card gifts (094)."""
from __future__ import annotations

import logging
from collections import defaultdict

import discord
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.views.manager_card_gift_claim import (
    CAMPAIGN_ID,
    ClaimManagerCardGiftView,
    ensure_pending_manager_gifts,
    manager_card_gifts_enabled,
    manager_gift_embed,
    set_manager_gift_dm_status,
)

logger = logging.getLogger(__name__)


async def notify_manager_card_gifts(bot: commands.Bot) -> None:
    """DM eligible managers once (idempotent via dm_status)."""
    db = await get_client()
    if not await manager_card_gifts_enabled(db):
        logger.info("Manager card gifts flag off — skip notify.")
        return

    pending_res = (
        await db.table("manager_card_gifts")
        .select("discord_id, gift_slot")
        .eq("campaign_id", CAMPAIGN_ID)
        .eq("claimed", False)
        .eq("dm_status", "pending")
        .execute()
    )
    rows = pending_res.data or []
    if not rows:
        logger.info("No manager card gifts to notify.")
        return

    by_owner: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        by_owner[int(row["discord_id"])].append(str(row["gift_slot"]))

    for owner_id, slots in by_owner.items():
        try:
            club = (
                await db.table("players")
                .select("discord_id")
                .eq("discord_id", owner_id)
                .maybe_single()
                .execute()
            )
            if not club or not club.data:
                logger.info(
                    "Manager gift skip DM for %s — no club yet (hub claim later).",
                    owner_id,
                )
                continue

            gifts = await ensure_pending_manager_gifts(owner_id)
            if not gifts:
                continue

            user = await bot.fetch_user(owner_id)
            if user is None:
                continue

            embed = manager_gift_embed(gifts)
            await user.send(embed=embed, view=ClaimManagerCardGiftView())
            await set_manager_gift_dm_status(owner_id, "sent")
            logger.info(
                "Sent manager card gift DM to %s (%s slot(s)).",
                owner_id,
                len(slots),
            )
        except discord.Forbidden:
            try:
                await set_manager_gift_dm_status(owner_id, "blocked")
            except Exception:
                logger.exception(
                    "Failed marking manager gift DM blocked for %s", owner_id
                )
            logger.warning(
                "DM blocked for manager gift owner %s — claim via /development.",
                owner_id,
            )
        except Exception:
            logger.exception("Failed notifying manager gift owner %s.", owner_id)

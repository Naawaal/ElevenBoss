# apps/discord_bot/tasks/academy_growth_job.py
"""Daily academy growth + age-out notifications (015)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from apps.discord_bot.core.card_payload import card_rpc_payload
from apps.discord_bot.db.client import get_client
from gacha import generate_youth_intake

logger = logging.getLogger(__name__)


async def run_daily_academy_growth(bot: commands.Bot) -> dict:
    db = await get_client()
    res = await db.rpc("process_daily_academy_growth").execute()
    summary = res.data or {}
    if not isinstance(summary, dict):
        summary = {"raw": summary}
    logger.info("Academy growth: %s", summary)

    for item in summary.get("age_out_promoted") or []:
        await _dm_age_out(bot, item, promoted=True)
    for item in summary.get("age_out_released") or []:
        await _dm_age_out(bot, item, promoted=False)

    # Optional scout-ready finalize + DM (hub remains source of truth if DMs off)
    summary["scout_reports_finalized"] = await _finalize_due_scouts(bot)
    return summary


async def _finalize_due_scouts(bot: commands.Bot) -> int:
    """Finalize elapsed scout timers and DM managers (tolerate Forbidden)."""
    db = await get_client()
    now = datetime.now(timezone.utc).isoformat()
    due_res = (
        await db.table("players")
        .select("discord_id, youth_academy_level, scouting_active_tier, scouting_finishes_at")
        .eq("is_ai", False)
        .not_.is_("scouting_finishes_at", "null")
        .lte("scouting_finishes_at", now)
        .execute()
    )
    finalized = 0
    for row in due_res.data or []:
        owner_id = int(row["discord_id"])
        try:
            level = int(row.get("youth_academy_level", 1))
            cards = generate_youth_intake(academy_level=level)
            payload = [card_rpc_payload(c) for c in cards[:3]]
            while len(payload) < 3:
                payload.append(payload[-1] if payload else {})
            tier = row.get("scouting_active_tier") or "standard"
            await db.rpc(
                "finalize_youth_scout_report",
                {"p_owner_id": owner_id, "p_prospects": payload[:3], "p_tier": tier},
            ).execute()
            finalized += 1
            await _dm_scout_ready(bot, owner_id, str(tier))
        except Exception:
            # Open report / race / already cleared — hub finalize covers the rest
            logger.debug("Scout finalize skip for %s", owner_id, exc_info=True)
    return finalized


async def _dm_scout_ready(bot: commands.Bot, owner_id: int, tier: str) -> None:
    text = (
        f"Your **{tier}** scout report is ready. "
        "Open **Manage Academy** (`/profile`) to sign up to **1** prospect."
    )
    try:
        user = await bot.fetch_user(owner_id)
        if user:
            await user.send(text)
    except discord.Forbidden:
        logger.info("DMs disabled for scout-ready owner %s", owner_id)
    except Exception:
        logger.exception("Scout-ready DM failed for owner %s", owner_id)


async def _dm_age_out(bot: commands.Bot, item: dict, *, promoted: bool) -> None:
    owner_id = item.get("owner_id")
    name = item.get("name", "A prospect")
    if not owner_id:
        return
    if promoted:
        text = (
            f"**{name}** aged out of the academy and was **auto-promoted** to your senior club. "
            "Assign them in `/squad` when ready."
        )
    else:
        text = (
            f"**{name}** aged out of the academy but your senior roster was full, "
            "so they were **released**. Free a senior slot next time via sell/release."
        )
    try:
        user = await bot.fetch_user(int(owner_id))
        if user:
            await user.send(text)
    except discord.Forbidden:
        logger.info("DMs disabled for age-out notify owner %s", owner_id)
    except Exception:
        logger.exception("Age-out DM failed for owner %s", owner_id)

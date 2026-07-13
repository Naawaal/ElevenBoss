# apps/discord_bot/tasks/youth_intake_notifier.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from apps.discord_bot.core.card_payload import card_rpc_payload
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.youth_intake_embeds import youth_intake_embed
from gacha import generate_youth_intake

logger = logging.getLogger(__name__)


async def run_season_youth_intake(bot: commands.Bot) -> dict:
    """Generate and persist weekly youth intake for all human managers."""
    db = await get_client()
    players_res = await db.table("players").select("discord_id, club_name, youth_academy_level").eq("is_ai", False).execute()
    managers = players_res.data or []
    summary = {"processed": 0, "skipped": 0, "failed": 0, "new_cards": 0, "intake_skipped_slots": 0}

    for row in managers:
        owner_id = int(row["discord_id"])
        try:
            academy_level = int(row.get("youth_academy_level", 1))
            cards = generate_youth_intake(academy_level=academy_level)
            payload = [card_rpc_payload(c) for c in cards]
            res = await db.rpc("process_youth_intake", {
                "p_owner_id": owner_id,
                "p_cards": payload,
            }).execute()
            result = res.data or {}
            if result.get("already_processed"):
                summary["skipped"] += 1
                continue
            summary["processed"] += 1
            seated_ids = result.get("card_ids") or []
            summary["new_cards"] += len(seated_ids)
            summary["intake_skipped_slots"] += int(result.get("skipped") or 0)
            # Only DM the seated subset by index order
            seated_n = int(result.get("seated") or len(seated_ids))
            seated_cards = cards[:seated_n]
            await _notify_manager(
                bot,
                owner_id,
                row.get("club_name"),
                seated_cards,
                seated=seated_n,
                skipped=int(result.get("skipped") or 0),
                slots_used=result.get("slots_used"),
                slots_cap=result.get("slots_cap"),
            )
        except Exception:
            summary["failed"] += 1
            logger.exception("Youth intake failed for owner %s", owner_id)

    logger.info(
        "Youth intake batch: processed=%s skipped=%s failed=%s new_cards=%s slot_skips=%s",
        summary["processed"],
        summary["skipped"],
        summary["failed"],
        summary["new_cards"],
        summary["intake_skipped_slots"],
    )
    return summary


async def _notify_manager(
    bot: commands.Bot,
    owner_id: int,
    club_name: str | None,
    cards: list,
    *,
    seated: int | None = None,
    skipped: int | None = None,
    slots_used: int | None = None,
    slots_cap: int | None = None,
) -> None:
    embed = youth_intake_embed(
        cards,
        club_name=club_name,
        seated=seated,
        skipped=skipped,
        slots_used=slots_used,
        slots_cap=slots_cap,
    )
    try:
        user = await bot.fetch_user(owner_id)
        if user:
            await user.send(embed=embed)
            db = await get_client()
            week_res = await db.rpc("current_intake_week").execute()
            intake_week = week_res.data
            if intake_week:
                await (
                    db.table("youth_intake_log")
                    .update({"notified_at": datetime.now(timezone.utc).isoformat()})
                    .eq("owner_id", owner_id)
                    .eq("intake_week", intake_week)
                    .execute()
                )
            return
    except discord.Forbidden:
        logger.info("DMs disabled for owner %s — youth intake stored (Manage Academy)", owner_id)
    except Exception:
        logger.exception("Failed to DM youth intake to owner %s", owner_id)

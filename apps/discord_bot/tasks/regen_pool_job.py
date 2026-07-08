# apps/discord_bot/tasks/regen_pool_job.py
"""Spawn scouting pool regens when high-OVR veterans retire (Phase D)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from apps.discord_bot.core.card_payload import scouting_pool_payload
from apps.discord_bot.db.client import get_client
from economy import GameConfig, scouting_purchase_price
from player_engine import generate_regen_from_retired

logger = logging.getLogger(__name__)

_REGEN_THRESHOLD_DEFAULT = 75


async def spawn_regens_from_recent_retirements(bot: commands.Bot | None = None) -> dict:
    """After season aging — list retired 75+ OVR cards as scouting pool players."""
    db = await get_client()
    threshold = _REGEN_THRESHOLD_DEFAULT
    try:
        cfg_res = await db.rpc("get_game_config", {"p_key": "regen_ovr_threshold"}).execute()
        if cfg_res.data is not None:
            threshold = int(cfg_res.data)
    except Exception:
        pass

    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    retired_res = await (
        db.table("player_cards")
        .select("*")
        .eq("is_retired", True)
        .gte("overall", threshold)
        .gte("retired_at", since)
        .execute()
    )
    retired_cards = retired_res.data or []

    from gacha.generator import _load_names
    names = _load_names()
    config = GameConfig()
    summary = {"spawned": 0, "skipped": 0, "failed": 0}

    for card in retired_cards:
        try:
            existing = await (
                db.table("scouting_pool_players")
                .select("id")
                .eq("source_card_id", card["id"])
                .maybe_single()
                .execute()
            )
            if existing and existing.data:
                summary["skipped"] += 1
                continue

            regen = generate_regen_from_retired(
                card,
                first_names=names["first"],
                last_names=names["last"],
            )
            age = regen["age"]
            price = scouting_purchase_price(
                regen["overall"],
                regen["rarity"],
                config,
                age=age,
                potential=regen["potential"],
            )
            payload = scouting_pool_payload(regen, list_price=price)
            await db.rpc("insert_scouting_pool_player", {"p_card": payload}).execute()
            summary["spawned"] += 1
        except Exception:
            summary["failed"] += 1
            logger.exception("Regen spawn failed for retired card %s", card.get("id"))

    logger.info(
        "Regen pool: spawned=%s skipped=%s failed=%s (threshold OVR %s)",
        summary["spawned"],
        summary["skipped"],
        summary["failed"],
        threshold,
    )
    return summary

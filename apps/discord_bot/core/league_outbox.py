# apps/discord_bot/core/league_outbox.py
"""Discord presentation outbox — never mutates competitive state."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def publish_pending_outbox(bot: Any, db: Any, *, limit: int = 50) -> int:
    """Publish unpublished outbox rows; swallow send errors."""
    try:
        res = await (
            db.table("league_outbox")
            .select("*")
            .is_("published_at", "null")
            .order("created_at")
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.exception("publish_pending_outbox: select failed")
        return 0

    rows = res.data or []
    published = 0
    for row in rows:
        ok = await _publish_one(bot, db, row)
        if ok:
            published += 1
    return published


async def _resolve_guild_for_payload(bot: Any, db: Any, payload: dict) -> Any | None:
    guild_id = payload.get("guild_id")
    if not guild_id and payload.get("season_id"):
        try:
            s = await db.table("league_seasons").select("league_id").eq(
                "id", payload["season_id"]
            ).maybe_single().execute()
            lid = (s.data or {}).get("league_id")
            if lid:
                lg = await db.table("leagues").select("guild_id").eq(
                    "id", lid
                ).maybe_single().execute()
                guild_id = (lg.data or {}).get("guild_id")
        except Exception:
            logger.debug("outbox guild resolve failed", exc_info=True)
    if not guild_id:
        return None
    guild = bot.get_guild(int(guild_id))
    if guild:
        return guild
    try:
        return await bot.fetch_guild(int(guild_id))
    except Exception:
        return None


def _format_event(event_type: str, payload: dict) -> str | None:
    sid = payload.get("season_id", "")
    if event_type == "registration_open":
        return (
            f"**Registration is open** for season `{sid}`! "
            "Use `/league` to join before the window closes."
        )
    if event_type == "registration_locked":
        return f"Registration is locked for season `{sid}`. Preparing the table…"
    if event_type == "registration_under_min":
        return (
            f"Registration closed without enough managers for season `{sid}`. "
            "Deposits (if any) will be refunded; next registration opens after offseason."
        )
    if event_type == "schedule_released":
        return (
            f"**Fixtures are live** for season `{sid}`! "
            "Check `/league hub` — play before your local matchday deadline."
        )
    if event_type == "matchday_open":
        md = payload.get("matchday", "?")
        return f"Matchday **{md}** is open. Play via `/league hub` before the deadline."
    if event_type == "season_completed":
        return (
            f"Season `{sid}` is complete — prizes and promotion applied. "
            "Enjoy the offseason before the next registration."
        )
    if event_type == "season_cancelled":
        return f"Season `{sid}` was cancelled (not a natural completion)."
    if event_type == "promotion_relegation":
        champ = payload.get("champion")
        promoted = payload.get("promoted") or []
        relegated = payload.get("relegated") or []
        return (
            f"**Division movement** (tier {payload.get('tier', '?')}): "
            f"champion `{champ}`, promoted {promoted}, relegated {relegated}."
        )
    return f"League update: `{event_type}` ({sid})"


async def _publish_one(bot: Any, db: Any, row: dict) -> bool:
    event_type = row.get("event_type") or ""
    payload = row.get("payload") or {}
    try:
        from apps.discord_bot.core.league_announce import _send_announce

        guild = await _resolve_guild_for_payload(bot, db, payload)
        body = _format_event(event_type, payload)
        if guild and body:
            await _send_announce(bot, db, guild, body)
        else:
            logger.info(
                "outbox event %s stored (no guild/channel) season=%s",
                event_type,
                payload.get("season_id"),
            )

        await (
            db.table("league_outbox")
            .update({
                "published_at": datetime.now(timezone.utc).isoformat(),
                "attempts": int(row.get("attempts") or 0) + 1,
            })
            .eq("id", row["id"])
            .execute()
        )
        return True
    except Exception:
        logger.exception("outbox publish failed for %s", row.get("id"))
        try:
            await (
                db.table("league_outbox")
                .update({"attempts": int(row.get("attempts") or 0) + 1})
                .eq("id", row["id"])
                .execute()
            )
        except Exception:
            pass
        return False

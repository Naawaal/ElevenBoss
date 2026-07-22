# apps/discord_bot/core/guild_resolver.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# V1 + legacy open statuses that may enter paused (US-42.5)
OPEN_PAUSEABLE_STATUSES: tuple[str, ...] = (
    "active",
    "registration",
    "registration_open",
    "registration_locked",
    "preparing",
)

# ponytail: per-process dedupe — resets on bot restart; upgrade path: persist pause_reason column
_logged_pause_attempts: set[str] = set()


async def resolve_bot_guild(
    bot: commands.Bot,
    guild_id: int,
) -> tuple[discord.Guild | None, bool]:
    """Resolve a guild from cache or API.

    Returns ``(guild, confirmed_unreachable)``. *confirmed_unreachable* is True when
    Discord reports the bot is not in the guild (NotFound/Forbidden).
    """
    guild = bot.get_guild(guild_id)
    if guild is not None:
        return guild, False

    try:
        guild = await bot.fetch_guild(guild_id)
        return guild, False
    except discord.NotFound:
        return None, True
    except discord.Forbidden:
        return None, True
    except discord.HTTPException as exc:
        if exc.status == 429 or (exc.status is not None and exc.status >= 500):
            logger.warning(
                "Transient Discord error resolving guild %s (HTTP %s)",
                guild_id,
                exc.status,
            )
            return None, False
        logger.warning("Discord HTTP %s resolving guild %s", exc.status, guild_id)
        return None, True
    except Exception:
        logger.warning("Failed to resolve guild %s", guild_id, exc_info=True)
        return None, False


async def pause_league_season(db, season_id: str, *, reason: str | None = None) -> bool:
    """Pause an open season with ``pause_started_at`` for resume rebase (US-42.5).

    Does not reset ``pause_started_at`` if already paused. Returns True if the season
    is paused after this call (newly or already).
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        res = await (
            db.table("league_seasons")
            .update({
                "status": "paused",
                "pause_started_at": now,
            })
            .eq("id", season_id)
            .in_("status", list(OPEN_PAUSEABLE_STATUSES))
            .execute()
        )
        if res.data:
            if reason:
                logger.warning(
                    "Paused season %s (%s)",
                    season_id,
                    reason,
                )
            return True
        cur = await (
            db.table("league_seasons")
            .select("status")
            .eq("id", season_id)
            .maybe_single()
            .execute()
        )
        return bool(cur and cur.data and cur.data.get("status") == "paused")
    except Exception:
        logger.exception("Failed to pause season %s", season_id)
        return False


async def pause_season_if_guild_unreachable(
    db,
    season_id: str,
    guild_id: int,
    reason: str,
) -> bool:
    """Pause an open season when the bot cannot reach its guild."""
    log_key = f"{season_id}:{reason}"
    paused = await pause_league_season(
        db, season_id, reason=f"guild={guild_id} {reason}"
    )
    if paused and log_key not in _logged_pause_attempts:
        _logged_pause_attempts.add(log_key)
        logger.warning(
            "Paused season %s for guild %s (%s)",
            season_id,
            guild_id,
            reason,
        )
    return paused


async def pause_seasons_for_guild(db, guild_id: int, reason: str) -> int:
    """Pause all open seasons for a guild's league.

    US-42.1: must not delete ``players`` / cards — guild context only.
    """
    league_res = await (
        db.table("leagues")
        .select("id")
        .eq("guild_id", guild_id)
        .maybe_single()
        .execute()
    )
    if not league_res or not league_res.data:
        return 0

    seasons_res = await (
        db.table("league_seasons")
        .select("id")
        .eq("league_id", league_res.data["id"])
        .in_("status", list(OPEN_PAUSEABLE_STATUSES))
        .execute()
    )
    paused = 0
    for season in seasons_res.data or []:
        if await pause_season_if_guild_unreachable(db, season["id"], guild_id, reason):
            paused += 1
    return paused

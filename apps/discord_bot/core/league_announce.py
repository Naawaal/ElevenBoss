# apps/discord_bot/core/league_announce.py
"""Guild announce-channel digests for League Automation (021)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


async def resolve_announce_targets(
    db: Any,
    guild: discord.Guild,
) -> tuple[discord.TextChannel | None, discord.Role | None, dict]:
    """Return (channel, role, guild_config row) from ``guild_config``."""
    res = await db.table("guild_config").select("*").eq("guild_id", guild.id).maybe_single().execute()
    config = res.data if res else {}
    if not config:
        return None, None, {}

    channel = None
    channel_id = config.get("league_channel_id")
    if channel_id:
        ch = guild.get_channel(int(channel_id))
        if ch is None:
            try:
                fetched = await guild.fetch_channel(int(channel_id))
                if isinstance(fetched, discord.TextChannel):
                    ch = fetched
            except Exception:
                ch = None
        if isinstance(ch, discord.TextChannel):
            channel = ch

    role = None
    role_id = config.get("announcement_role_id")
    if role_id:
        role = guild.get_role(int(role_id))

    return channel, role, config


async def set_automation_last_error(db: Any, guild_id: int, message: str | None) -> None:
    try:
        await db.table("guild_config").update({"automation_last_error": message}).eq(
            "guild_id", guild_id
        ).execute()
    except Exception:
        logger.debug("automation_last_error update failed guild=%s", guild_id, exc_info=True)


# Back-compat alias used by orchestrator imports
_set_automation_error = set_automation_last_error


async def _clear_automation_error_if_set(db: Any, guild_id: int, config: dict) -> None:
    if config.get("automation_last_error"):
        await _set_automation_error(db, guild_id, None)


async def _send_announce(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    content: str,
) -> bool:
    """Post to announce channel with optional role ping. Never raises to callers."""
    try:
        channel, role, config = await resolve_announce_targets(db, guild)
        if not channel:
            await _set_automation_error(db, guild.id, "League announce channel missing or inaccessible")
            return False

        body = content
        if role:
            body = f"{role.mention}\n\n{content}"

        await channel.send(
            content=body,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await _clear_automation_error_if_set(db, guild.id, config)
        return True
    except Exception as exc:
        logger.warning("League announce failed guild=%s: %s", guild.id, exc, exc_info=True)
        try:
            await _set_automation_error(db, guild.id, f"Announce send failed: {exc}"[:500])
        except Exception:
            pass
        return False


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


async def post_registration_open(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    *,
    season_number: int,
    closes_at: datetime,
) -> bool:
    body = (
        f"Season {season_number} registration is open! Use `/league` to join. "
        f"Closes <t:{_ts(closes_at)}:F> (<t:{_ts(closes_at)}:R>)."
    )
    return await _send_announce(bot, db, guild, body)


async def post_registration_failed_under_min(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    *,
    season_number: int,
    min_humans: int,
    human_count: int,
    next_at: datetime,
) -> bool:
    body = (
        f"Season {season_number} registration closed — need at least {min_humans} managers "
        f"(had {human_count}). Next registration: Monday <t:{_ts(next_at)}:F>."
    )
    return await _send_announce(bot, db, guild, body)


async def post_season_start_digest(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    *,
    season_number: int,
    division_count: int,
    total_matchdays: int = 14,
) -> bool:
    div_line = (
        f"**{division_count}** Seasonal Divisions (8 clubs each)"
        if division_count > 1
        else "1 division table (8 clubs)"
    )
    body = (
        f"**Season {season_number}** is live!\n"
        f"⏱ **14-day** League Dynamics — play each matchday **before 00:00 UTC**.\n"
        f"📊 {div_line} · **{total_matchdays}** matchdays\n"
        f"Check `/league hub` for fixtures and standings."
    )
    return await _send_announce(bot, db, guild, body)


async def post_daily_tick_digest(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    *,
    season_id: str,
    completed_matchday: int,
    total_matchdays: int,
    season_completed: bool = False,
) -> bool:
    """Standings + optional MoMD line for matchday settlement (announce channel)."""
    lines: list[str] = [f"**Matchday {completed_matchday} complete**"]

    try:
        award_res = await (
            db.table("league_matchday_manager_awards")
            .select("player_id, coins_awarded, fixture_id, margin")
            .eq("season_id", season_id)
            .eq("matchday", completed_matchday)
            .maybe_single()
            .execute()
        )
        if award_res and award_res.data:
            row = award_res.data
            club = f"Club {row.get('player_id')}"
            pid = row.get("player_id")
            if pid is not None:
                p_res = await db.table("players").select("club_name").eq(
                    "discord_id", int(pid)
                ).maybe_single().execute()
                if p_res and p_res.data:
                    club = p_res.data.get("club_name") or club
            coins = int(row.get("coins_awarded") or 2000)
            score = ""
            if row.get("fixture_id"):
                f_res = await db.table("league_fixtures").select(
                    "home_score, away_score"
                ).eq("id", row["fixture_id"]).maybe_single().execute()
                if f_res and f_res.data:
                    score = f" ({f_res.data.get('home_score', 0)}–{f_res.data.get('away_score', 0)})"
            lines.append(f"🏅 Manager of the Matchday: **{club}**{score} — +{coins} coins")
    except Exception:
        logger.debug("MoMD award lookup for digest failed", exc_info=True)

    try:
        from apps.discord_bot.cogs.league_cog import fetch_standings
        from leagues import format_standings_table

        fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season_id).execute()
        all_fixtures = fixtures_res.data or []
        parts_res = await db.table("league_participants").select("division_tier").eq(
            "season_id", season_id
        ).execute()
        tiers = sorted({int(p.get("division_tier") or 1) for p in (parts_res.data or [])}) or [1]

        tables: list[str] = []
        for t in tiers:
            st = await fetch_standings(db, season_id, division_tier=t)
            header = f"— Division {t} —\n" if len(tiers) > 1 else ""
            tables.append(header + format_standings_table(st, all_fixtures, limit=8))
        if tables:
            lines.append("\n".join(tables))
    except Exception:
        logger.debug("Standings table for digest failed", exc_info=True)

    if not season_completed and completed_matchday < total_matchdays:
        lines.append(f"Matchday {completed_matchday + 1} open — play before 00:00 UTC")

    return await _send_announce(bot, db, guild, "\n".join(lines))


async def post_season_concluded(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    *,
    season_number: int,
    registration_opening: bool = False,
) -> bool:
    body = f"**Season {season_number}** has concluded!"
    if registration_opening:
        body += f"\nRegistration for Season {season_number + 1} is opening…"
    return await _send_announce(bot, db, guild, body)

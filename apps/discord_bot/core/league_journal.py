# apps/discord_bot/core/league_journal.py
"""League Journal + MatchDay thread helpers (US-26, US-28)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import discord
from discord.ext import commands

from apps.discord_bot.core.locks import get_guild_thread_lock

logger = logging.getLogger(__name__)

THREAD_ARCHIVE_DAYS = 10080  # 7 days
JOURNAL_THREAD_NAME = "League Journal"
MATCHDAY_THREAD_NAME = "MatchDay"

JOURNAL_INTRO = discord.Embed(
    title="🏆 ElevenBoss League Journal",
    description=(
        "Welcome to the official League Journal! Here you will find live match tickers, "
        "results, and season summaries.\n\n"
        "**League Rules & Info:**\n"
        "• Play matches using `/league hub` before the matchday window ends.\n"
        "• Unplayed matches will be auto-simulated at the end of the window.\n"
        "• Win = 3 pts, Draw = 1 pt, Loss = 0 pts.\n"
        "• Season standings are separate from weekly Division Rank points."
    ),
    color=0x00FF87,
)

DUAL_JOURNAL_INTRO = discord.Embed(
    title="📊 League Journal — Official Record",
    description=(
        "Pinned standings and final scores for this season.\n"
        "Live commentary streams in the **MatchDay** thread."
    ),
    color=0x3498DB,
)

MATCHDAY_INTRO = discord.Embed(
    title="🎙️ MatchDay — Live Commentary",
    description="All live league match streams, pitch visuals, and post-match reports appear here.",
    color=0x00FF87,
)


async def announcement_role_mention(guild: discord.Guild, db) -> str:
    """Return ``<@&role_id>`` for configured league announcement role, or empty string."""
    try:
        config_res = await db.table("guild_config").select("announcement_role_id").eq(
            "guild_id", guild.id
        ).maybe_single().execute()
        role_id = (config_res.data or {}).get("announcement_role_id") if config_res else None
        if role_id and guild.get_role(role_id):
            return f"<@&{role_id}>"
    except Exception:
        logger.debug("announcement_role_mention failed", exc_info=True)
    return ""


@dataclass
class SeasonThreads:
    format: str  # 'dual_v2' | 'legacy'
    commentary_thread: discord.Thread
    journal_thread: discord.Thread | None
    journal_standings_message_id: int | None


async def _fetch_thread(guild: discord.Guild, thread_id: int | None) -> discord.Thread | None:
    if not thread_id:
        return None
    thread = guild.get_thread(thread_id)
    if thread:
        return thread
    try:
        ch = await guild.fetch_channel(thread_id)
        return ch if isinstance(ch, discord.Thread) else None
    except (discord.NotFound, discord.HTTPException):
        return None


async def _lock_thread(thread: discord.Thread) -> None:
    try:
        await thread.edit(locked=True)
    except discord.HTTPException:
        logger.debug("Could not lock thread %s", thread.id, exc_info=True)


async def _create_locked_thread_from_message(
    anchor: discord.Message,
    name: str,
) -> discord.Thread | None:
    try:
        thread = await anchor.create_thread(name=name, auto_archive_duration=THREAD_ARCHIVE_DAYS)
        await _lock_thread(thread)
        return thread
    except Exception:
        logger.exception("Failed to create thread %s from message %s", name, anchor.id)
        return None


async def get_or_create_league_journal(
    bot: commands.Bot,
    db,
    guild: discord.Guild,
    *,
    league_channel_id: int | None = None,
) -> discord.Thread | None:
    """Resolve, create, or recreate the legacy centralized journal thread."""
    guild_id = guild.id
    config_res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
    config = config_res.data if config_res else None
    if not config:
        return None

    channel_id = league_channel_id or config.get("league_channel_id")
    if not channel_id:
        return None

    announcement_channel = guild.get_channel(channel_id)
    if not announcement_channel:
        return None

    thread_id = config.get("league_updates_thread_id")
    thread = await _fetch_thread(guild, thread_id)
    if thread:
        return thread

    lock = await get_guild_thread_lock(guild_id)
    async with lock:
        config_res = await db.table("guild_config").select("league_updates_thread_id").eq("guild_id", guild_id).maybe_single().execute()
        tid = (config_res.data or {}).get("league_updates_thread_id")
        thread = await _fetch_thread(guild, tid)
        if thread:
            return thread

        try:
            thread = await announcement_channel.create_thread(
                name="📰 league-journal",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=60,
            )
            first_msg = await thread.send(embed=JOURNAL_INTRO)
            try:
                await first_msg.pin()
            except discord.HTTPException:
                pass
            try:
                everyone_role = announcement_channel.guild.default_role
                overwrites = announcement_channel.overwrites_for(everyone_role)
                if overwrites.add_reactions is not True:
                    overwrites.add_reactions = True
                    await announcement_channel.set_permissions(everyone_role, overwrite=overwrites)
            except discord.HTTPException:
                pass
            await db.table("guild_config").update({"league_updates_thread_id": thread.id}).eq("guild_id", guild_id).execute()
            return thread
        except Exception:
            logger.exception("Failed to create League Journal thread for guild %s", guild_id)
            return None


async def create_season_threads(
    bot: commands.Bot,
    db,
    guild: discord.Guild,
    channel: discord.abc.Messageable,
    *,
    season_id: str,
    league_name: str,
    initial_table_text: str,
    announcement_message_id: int | None = None,
) -> SeasonThreads | None:
    """Create dual locked threads at season start and seed journal standings."""
    journal_name = JOURNAL_THREAD_NAME
    matchday_name = MATCHDAY_THREAD_NAME

    try:
        journal_anchor = await channel.send("📊 **Official league standings and results** ↓")
        journal_thread = await _create_locked_thread_from_message(journal_anchor, journal_name)
        if not journal_thread:
            return None

        intro_msg = await journal_thread.send(embed=DUAL_JOURNAL_INTRO)
        try:
            await intro_msg.pin()
        except discord.HTTPException:
            pass

        standings_msg = await post_journal_standings(
            journal_thread, initial_table_text, matchday=1
        )

        matchday_anchor = await channel.send("🎙️ **Live match commentary** ↓")
        matchday_thread = await _create_locked_thread_from_message(matchday_anchor, matchday_name)
        if not matchday_thread:
            return None

        md_intro = await matchday_thread.send(embed=MATCHDAY_INTRO)
        try:
            await md_intro.pin()
        except discord.HTTPException:
            pass

        standings_id = standings_msg.id if standings_msg else None
        await db.table("league_seasons").update({
            "announcement_message_id": announcement_message_id,
            "journal_thread_id": journal_thread.id,
            "matchday_thread_id": matchday_thread.id,
            "journal_standings_message_id": standings_id,
            "thread_format": "dual_v2",
        }).eq("id", season_id).execute()

        return SeasonThreads(
            format="dual_v2",
            commentary_thread=matchday_thread,
            journal_thread=journal_thread,
            journal_standings_message_id=standings_id,
        )
    except Exception:
        logger.exception("create_season_threads failed for season %s", season_id)
        return None


async def resolve_season_threads(
    bot: commands.Bot,
    db,
    guild: discord.Guild,
    season_id: str,
) -> SeasonThreads | None:
    """Resolve threads for a season; legacy seasons fall back to single journal."""
    season_res = await db.table("league_seasons").select(
        "thread_format, journal_thread_id, matchday_thread_id, journal_standings_message_id"
    ).eq("id", season_id).maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        return None

    if season.get("thread_format") != "dual_v2":
        legacy = await get_or_create_league_journal(bot, db, guild)
        if not legacy:
            return None
        return SeasonThreads(
            format="legacy",
            commentary_thread=legacy,
            journal_thread=None,
            journal_standings_message_id=None,
        )

    journal = await _fetch_thread(guild, season.get("journal_thread_id"))
    matchday = await _fetch_thread(guild, season.get("matchday_thread_id"))
    if journal and matchday:
        return SeasonThreads(
            format="dual_v2",
            commentary_thread=matchday,
            journal_thread=journal,
            journal_standings_message_id=season.get("journal_standings_message_id"),
        )

    logger.warning("Season %s dual threads missing — falling back to legacy journal", season_id)
    legacy = await get_or_create_league_journal(bot, db, guild)
    if not legacy:
        return None
    return SeasonThreads(
        format="legacy",
        commentary_thread=legacy,
        journal_thread=None,
        journal_standings_message_id=None,
    )


async def persist_journal_standings_message_id(db, season_id: str, message_id: int) -> None:
    try:
        await db.table("league_seasons").update({
            "journal_standings_message_id": message_id,
        }).eq("id", season_id).execute()
    except Exception:
        logger.debug("persist_journal_standings_message_id failed", exc_info=True)


async def archive_season_threads(
    guild: discord.Guild,
    season_row: dict,
    *,
    season_number: int,
) -> None:
    """Lock and archive dual_v2 threads at season end."""
    if season_row.get("thread_format") != "dual_v2":
        return
    for key in ("journal_thread_id", "matchday_thread_id"):
        thread = await _fetch_thread(guild, season_row.get(key))
        if not thread:
            continue
        try:
            suffix = "journal" if key == "journal_thread_id" else "matchday"
            await thread.edit(
                name=f"🏆-s{season_number}-{suffix}-concluded",
                locked=True,
                archived=True,
            )
        except Exception:
            logger.warning("Failed to archive thread %s", thread.id, exc_info=True)


async def post_journal_standings(
    thread: discord.Thread,
    table_text: str,
    matchday: int,
    *,
    existing_message_id: int | None = None,
) -> discord.Message | None:
    """Post or edit standings embed in the journal thread."""
    embed = discord.Embed(
        title=f"📊 Live Table — Matchday {matchday}",
        description=f"```\n{table_text}\n```",
        color=0x3498DB,
    )
    try:
        if existing_message_id:
            msg = await thread.fetch_message(existing_message_id)
            await msg.edit(embed=embed)
            return msg
        return await thread.send(embed=embed)
    except Exception:
        logger.debug("post_journal_standings failed", exc_info=True)
        return None


async def post_journal_result_line(
    thread: discord.Thread,
    matchday: int,
    home_name: str,
    away_name: str,
    home_score: int,
    away_score: int,
) -> None:
    """Compact result line for the official record thread (no role ping)."""
    try:
        await thread.send(
            f"**MD{matchday}** · {home_name} **{home_score}–{away_score}** {away_name}"
        )
    except Exception:
        logger.debug("post_journal_result_line failed", exc_info=True)


async def post_matchday_result_line(
    thread: discord.Thread,
    guild: discord.Guild,
    db,
    matchday: int,
    home_name: str,
    away_name: str,
    home_score: int,
    away_score: int,
) -> None:
    """Announce a finished fixture in MatchDay with announcement role ping."""
    role_ping = await announcement_role_mention(guild, db)
    line = f"**MD{matchday}** · {home_name} **{home_score}–{away_score}** {away_name}"
    content = f"{role_ping}\n{line}" if role_ping else line
    try:
        await thread.send(
            content,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
    except Exception:
        logger.debug("post_matchday_result_line failed", exc_info=True)


async def post_matchday_standings_table(
    thread: discord.Thread,
    table_text: str,
    matchday: int,
) -> discord.Message | None:
    """Post a fresh standings embed when a matchday completes."""
    embed = discord.Embed(
        title=f"📊 Matchday {matchday} — Standings",
        description=f"```\n{table_text}\n```",
        color=0x3498DB,
    )
    try:
        return await thread.send(embed=embed)
    except Exception:
        logger.debug("post_matchday_standings_table failed", exc_info=True)
        return None


async def notify_matchday_complete(
    bot: commands.Bot,
    guild: discord.Guild,
    db,
    season_id: str,
    completed_matchday: int,
) -> None:
    """Push updated standings to MatchDay when all fixtures in a matchday finish."""
    threads = await resolve_season_threads(bot, db, guild, season_id)
    if not threads or threads.format != "dual_v2":
        return
    try:
        from apps.discord_bot.cogs.league_cog import fetch_standings
        from leagues import format_standings_table

        fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season_id).execute()
        all_fixtures = fixtures_res.data or []
        standings = await fetch_standings(db, season_id)
        table_text = format_standings_table(standings, all_fixtures, limit=10)
        role_ping = await announcement_role_mention(guild, db)
        header = f"{role_ping}\n\n" if role_ping else ""
        await threads.commentary_thread.send(
            f"{header}✅ **Matchday {completed_matchday} complete** — updated standings:",
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        msg = await post_matchday_standings_table(
            threads.commentary_thread, table_text, completed_matchday
        )
    except Exception:
        logger.exception("notify_matchday_complete failed for season %s", season_id)


# Legacy alias
post_live_standings = post_journal_standings

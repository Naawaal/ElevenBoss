# apps/discord_bot/core/match_recovery.py
"""Boot-time recovery for interrupted match runs."""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from apps.discord_bot.core.match_runs import abandon_run
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed

logger = logging.getLogger(__name__)


async def _resolve_thread(bot: commands.Bot, run: dict) -> discord.Thread | None:
    guild_id = run.get("guild_id")
    thread_id = run.get("thread_id")
    if not guild_id or not thread_id:
        return None
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return None
    thread = guild.get_thread(int(thread_id))
    if thread:
        return thread
    try:
        ch = await bot.fetch_channel(int(thread_id))
        return ch if isinstance(ch, discord.Thread) else None
    except (discord.NotFound, discord.HTTPException):
        return None


async def _notify_participants(bot: commands.Bot, run: dict, message: str) -> None:
    seen: set[int] = set()
    for key in ("active_discord_id", "home_discord_id", "away_discord_id"):
        uid = run.get(key)
        if not uid or uid in seen:
            continue
        seen.add(int(uid))
        try:
            user = await bot.fetch_user(int(uid))
            await user.send(message)
        except Exception:
            logger.debug("Could not DM user %s about abandoned match", uid)


async def _abandon_ephemeral_run(bot: commands.Bot, db, run: dict) -> None:
    thread = await _resolve_thread(bot, run)
    if thread:
        try:
            await thread.send(
                embed=error_embed(
                    "⚠️ **Match abandoned** due to a technical interruption.\n"
                    "No rewards were applied. You can start a new match."
                )
            )
            await thread.edit(locked=True, archived=True)
        except Exception:
            logger.warning("Failed to post abandon notice to thread %s", run.get("thread_id"))
    await _notify_participants(
        bot,
        run,
        "Your ElevenBoss match was interrupted by a restart. No rewards were applied — you can play again.",
    )
    await abandon_run(db, run["id"])
    logger.info("Abandoned %s match run %s", run.get("run_type"), run["id"])


async def _recover_league_run(bot: commands.Bot, db, run: dict) -> None:
    from apps.discord_bot.cogs.battle_cog import LeagueMatchHandler, run_league_match_simulation

    fixture_id = run.get("fixture_id")
    if not fixture_id:
        await abandon_run(db, run["id"])
        return

    f_res = await db.table("league_fixtures").select(
        "*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)"
    ).eq("id", fixture_id).maybe_single().execute()
    fixture = f_res.data if f_res else None
    if not fixture:
        await abandon_run(db, run["id"])
        return

    if fixture.get("is_played"):
        from apps.discord_bot.core.match_runs import complete_run
        await complete_run(db, run["id"], home_score=fixture.get("home_score") or 0, away_score=fixture.get("away_score") or 0)
        logger.info("League run %s already played; marked completed", run["id"])
        return

    guild_id = run.get("guild_id")
    guild = bot.get_guild(int(guild_id)) if guild_id else None
    if not guild:
        logger.warning("Cannot recover league run %s — guild %s unavailable", run["id"], guild_id)
        return

    thread = await _resolve_thread(bot, run)
    if not thread:
        logger.warning("Cannot recover league run %s — thread missing", run["id"])
        return

    snapshot = run.get("squad_snapshot") or {}
    home_name = snapshot.get("home_name", "Home")
    away_name = snapshot.get("away_name", "Away")

    try:
        await thread.send(
            embed=discord.Embed(
                title="⚠️ Match interrupted — completing result",
                description=(
                    f"**{home_name}** vs **{away_name}** was interrupted by a bot restart.\n"
                    "The fixture is being finalized now. The score may differ from the live ticker."
                ),
                color=0xFFCC00,
            )
        )
    except Exception:
        pass

    handler = LeagueMatchHandler(thread, fixture_id=fixture_id, season_id=fixture["season_id"])
    await run_league_match_simulation(
        bot=bot,
        db=db,
        guild=guild,
        fixture=fixture,
        active_player_id=run.get("active_discord_id"),
        handler=handler,
        sim_seed=int(run["sim_seed"]),
        run_id=run["id"],
        recovery=True,
        silent=True,
    )
    logger.info("Recovered league run %s for fixture %s", run["id"], fixture_id)


async def recover_interrupted_matches(bot: commands.Bot) -> None:
    db = await get_client()
    res = await db.table("match_runs").select("*").in_(
        "status", ["streaming", "completing"]
    ).execute()
    runs = res.data or []
    if not runs:
        logger.info("No interrupted match runs to recover.")
        return

    logger.info("Recovering %d interrupted match run(s)...", len(runs))
    for run in runs:
        try:
            if run.get("run_type") == "league":
                await _recover_league_run(bot, db, run)
            else:
                await _abandon_ephemeral_run(bot, db, run)
        except Exception:
            logger.exception("Recovery failed for match run %s", run.get("id"))

    # Clear stale per-player locks; active runs are now completed or abandoned.
    await db.table("match_locks").delete().neq("discord_id", 0).execute()
    logger.info("Match recovery complete; stale locks cleared.")

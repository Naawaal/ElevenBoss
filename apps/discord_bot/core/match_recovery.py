# apps/discord_bot/core/match_recovery.py
"""Boot-time recovery for interrupted match runs (US-42.4)."""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands
from player_engine import classify_interrupted_run

from apps.discord_bot.core.guild_resolver import resolve_bot_guild
from apps.discord_bot.core.match_runs import (
    abandon_run,
    complete_run,
    fetch_match_reward_row,
    reconcile_orphaned_match_locks,
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed

logger = logging.getLogger(__name__)


async def _resolve_thread(bot: commands.Bot, run: dict) -> discord.Thread | None:
    guild_id = run.get("guild_id")
    thread_id = run.get("thread_id")
    if not guild_id or not thread_id:
        return None
    guild = (await resolve_bot_guild(bot, int(guild_id)))[0]
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


async def _run_rewards_applied(db, run: dict) -> bool:
    """True if durable match_history exists for this run (bot/league)."""
    run_id = run.get("id")
    if not run_id:
        return False
    run_type = run.get("run_type")
    if run_type == "friendly":
        return False
    if run_type == "league":
        fixture_id = run.get("fixture_id")
        if fixture_id:
            f_res = await db.table("league_fixtures").select("is_played").eq(
                "id", fixture_id
            ).maybe_single().execute()
            if f_res and f_res.data and f_res.data.get("is_played"):
                return True
        for key in ("home_discord_id", "away_discord_id", "active_discord_id"):
            uid = run.get(key)
            if not uid:
                continue
            row = await fetch_match_reward_row(db, int(uid), run_id=run_id)
            if row:
                return True
            if fixture_id:
                row = await fetch_match_reward_row(db, int(uid), fixture_id=fixture_id)
                if row:
                    return True
        return False
    # bot / other
    uid = run.get("active_discord_id") or run.get("home_discord_id")
    if not uid:
        return False
    row = await fetch_match_reward_row(db, int(uid), run_id=run_id)
    return bool(row)


async def _complete_ephemeral_run(bot: commands.Bot, db, run: dict) -> None:
    await complete_run(
        db,
        run["id"],
        home_score=int(run.get("home_score") or 0),
        away_score=int(run.get("away_score") or 0),
    )
    logger.info(
        "Completed interrupted %s match run %s (rewards already applied)",
        run.get("run_type"),
        run["id"],
    )
    await _notify_participants(
        bot,
        run,
        "Your ElevenBoss match was interrupted after rewards were saved. "
        "Your coins/XP are safe — the match is marked complete.",
    )


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
            if thread.guild:
                from apps.discord_bot.core.thread_permissions import archive_thread_after_delay

                asyncio.create_task(archive_thread_after_delay(thread, thread.guild, delay=0))
        except Exception:
            logger.warning("Failed to post abandon notice to thread %s", run.get("thread_id"))
    await _notify_participants(
        bot,
        run,
        "Your ElevenBoss match was interrupted by a restart. No rewards were applied — you can play again.",
    )
    await abandon_run(db, run["id"], reason="boot_recovery")
    logger.info("Abandoned %s match run %s", run.get("run_type"), run["id"])


async def _recover_ephemeral_run(bot: commands.Bot, db, run: dict) -> None:
    rewards = await _run_rewards_applied(db, run)
    action = classify_interrupted_run(
        status=str(run.get("status") or ""),
        rewards_applied=rewards,
    )
    if action == "complete":
        await _complete_ephemeral_run(bot, db, run)
    elif action == "abandon":
        await _abandon_ephemeral_run(bot, db, run)
    else:
        logger.info("No-op recovery for run %s status=%s", run.get("id"), run.get("status"))


async def _recover_league_run(bot: commands.Bot, db, run: dict) -> None:
    from apps.discord_bot.cogs.battle_cog import LeagueMatchHandler, run_league_match_simulation
    from apps.discord_bot.core.league_journal import resolve_season_threads

    fixture_id = run.get("fixture_id")
    if not fixture_id:
        await abandon_run(db, run["id"], reason="league_recovery_no_fixture")
        return

    f_res = await db.table("league_fixtures").select(
        "*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)"
    ).eq("id", fixture_id).maybe_single().execute()
    fixture = f_res.data if f_res else None
    if not fixture:
        await abandon_run(db, run["id"], reason="league_recovery_fixture_missing")
        return

    if fixture.get("is_played"):
        await complete_run(
            db,
            run["id"],
            home_score=fixture.get("home_score") or 0,
            away_score=fixture.get("away_score") or 0,
        )
        logger.info("League run %s already played; marked completed", run["id"])
        return

    # Rewards already applied but fixture not marked — complete, don't re-sim
    if await _run_rewards_applied(db, run):
        await complete_run(
            db,
            run["id"],
            home_score=int(run.get("home_score") or 0),
            away_score=int(run.get("away_score") or 0),
        )
        logger.info("League run %s had rewards; marked completed without re-sim", run["id"])
        return

    guild_id = run.get("guild_id")
    guild = (await resolve_bot_guild(bot, int(guild_id)))[0] if guild_id else None
    if not guild:
        logger.warning(
            "Cannot recover league run %s — guild %s unavailable; abandoning",
            run["id"],
            guild_id,
        )
        await abandon_run(db, run["id"], reason="league_recovery_no_guild")
        return

    season_threads = await resolve_season_threads(bot, db, guild, fixture["season_id"])
    if not season_threads:
        thread = await _resolve_thread(bot, run)
        if not thread:
            logger.warning(
                "Cannot recover league run %s — thread missing; abandoning",
                run["id"],
            )
            await abandon_run(db, run["id"], reason="league_recovery_no_thread")
            return
        season_threads_commentary = thread
        journal_thread = None
        journal_standings_msg_id = None
    else:
        season_threads_commentary = season_threads.commentary_thread
        journal_thread = season_threads.journal_thread
        journal_standings_msg_id = season_threads.journal_standings_message_id

    snapshot = run.get("squad_snapshot") or {}
    home_name = snapshot.get("home_name", "Home")
    away_name = snapshot.get("away_name", "Away")

    try:
        await season_threads_commentary.send(
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

    handler = LeagueMatchHandler(
        commentary_thread=season_threads_commentary,
        fixture_id=fixture_id,
        season_id=fixture["season_id"],
        journal_thread=journal_thread,
        journal_standings_msg_id=journal_standings_msg_id,
    )
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
    """
    Boot recovery. League v3 runs re-sim via battle_cog with
    `load_run_decision_intents` when engine_version=nss_v3 (T058).
    """
    db = await get_client()
    res = await db.table("match_runs").select("*").in_(
        "status", ["streaming", "completing"]
    ).execute()
    runs = res.data or []
    if not runs:
        logger.info("No interrupted match runs to recover.")
        deleted = await reconcile_orphaned_match_locks(db)
        if deleted:
            logger.info("Reconciled %s orphaned match lock(s).", deleted)
        return

    logger.info("Recovering %d interrupted match run(s)...", len(runs))
    for run in runs:
        try:
            if run.get("run_type") == "league":
                await _recover_league_run(bot, db, run)
            else:
                await _recover_ephemeral_run(bot, db, run)
        except Exception:
            logger.exception("Recovery failed for match run %s", run.get("id"))
            try:
                action = classify_interrupted_run(
                    status=str(run.get("status") or "streaming"),
                    rewards_applied=await _run_rewards_applied(db, run),
                )
                if action == "complete":
                    await complete_run(
                        db,
                        run["id"],
                        home_score=int(run.get("home_score") or 0),
                        away_score=int(run.get("away_score") or 0),
                    )
                elif action == "abandon":
                    await abandon_run(db, run["id"], reason="recovery_exception")
            except Exception:
                logger.exception("Fallback terminalization failed for %s", run.get("id"))

    deleted = await reconcile_orphaned_match_locks(db)
    logger.info("Match recovery complete; reconciled %s orphaned lock(s).", deleted)

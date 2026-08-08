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
        return
    if action != "abandon":
        logger.info("No-op recovery for run %s status=%s", run.get("id"), run.get("status"))
        return

    # Feature 057: competitive bot mid-match — silent deterministic settle instead of abandon
    if (
        run.get("run_type") == "bot"
        and isinstance(run.get("competitive_state"), dict)
        and run.get("sim_seed") is not None
    ):
        try:
            await _recover_competitive_bot_run(bot, db, run)
            return
        except Exception:
            logger.exception(
                "Competitive bot recovery failed for %s — abandoning", run.get("id")
            )

    await _abandon_ephemeral_run(bot, db, run)


async def _recover_competitive_bot_run(bot: commands.Bot, db, run: dict) -> None:
    """Re-sim with same seed (deterministic), apply rewards once, complete run."""
    from match_engine import MatchState, collect_match_events, build_bot_match_squad
    from match_engine.v3.adapters import collect_match_events_v3
    from apps.discord_bot.core.match_cards import ordered_cards_to_match_squad
    from apps.discord_bot.core.match_rewards import apply_bot_match_rewards
    from apps.discord_bot.core.squad_fetch import fetch_squad_xi
    from apps.discord_bot.core.competitive_match import (
        competitive_result_str,
        dismissals_for_rpc,
        snapshot_from_state,
    )
    from apps.discord_bot.core.competitive_flags import competitive_et_multipliers
    from apps.discord_bot.core.match_runs import ENGINE_NSS_V3
    from apps.discord_bot.core.league_lp import (
        division_rank_points,
        global_lp_delta,
    )

    uid = int(run.get("active_discord_id") or run.get("home_discord_id") or 0)
    if not uid:
        await abandon_run(db, run["id"], reason="competitive_recovery_no_user")
        return

    player_res = await db.table("players").select("*").eq("discord_id", uid).maybe_single().execute()
    player = player_res.data if player_res else None
    if not player:
        await abandon_run(db, run["id"], reason="competitive_recovery_no_player")
        return

    _, _, active_cards = await fetch_squad_xi(db, uid)
    if len(active_cards) != 11:
        await abandon_run(db, run["id"], reason="competitive_recovery_bad_xi")
        return

    match_cards = await ordered_cards_to_match_squad(db, active_cards)
    my_rating = sum(p.overall for p in match_cards) / len(match_cards)
    snap = run.get("squad_snapshot") or {}
    opp_rating = float(snap.get("opp_rating") or my_rating)
    opp_name = str(snap.get("opp_name") or "AI Club")
    sim_seed = int(run["sim_seed"])
    fatigue_m, injury_m = await competitive_et_multipliers(db)

    state = MatchState(home_rating=my_rating, away_rating=opp_rating)
    state.competitive_enabled = True
    state.et_fatigue_mult = fatigue_m
    state.et_injury_mult = injury_m
    state.sim_seed = sim_seed
    state.injuries_enabled = False  # silent recovery — no interactive injury pauses
    state.interactive_sides = []

    opp_squad = build_bot_match_squad(int(opp_rating), __import__("random").Random(sim_seed ^ 0xB075AD))
    engine_version = run.get("engine_version") or "nss_v2"
    if engine_version == ENGINE_NSS_V3:
        state, events, _canon = await collect_match_events_v3(
            state, match_cards, opp_squad, player["club_name"], opp_name, sim_seed=sim_seed
        )
    else:
        state, events = await collect_match_events(
            state, match_cards, opp_squad, player["club_name"], opp_name, sim_seed=sim_seed
        )

    div_res = await db.table("global_divisions").select("*").order("min_lp", desc=True).execute()
    divisions = div_res.data or []
    user_lp = player.get("global_lp", 0)
    current_div = {"name": "Bronze III", "win_coins": 100}
    for div in divisions:
        if user_lp >= div["min_lp"]:
            current_div = div
            break

    res_str = competitive_result_str(state)
    points_earned = division_rank_points(res_str)
    lp_delta = global_lp_delta(res_str)
    key_events = [
        {"minute": e.get("minute"), "type": e.get("type"), "actor": e.get("actor"), "team": e.get("team")}
        for e in events
        if e.get("type") in ("GOAL", "FULL_TIME", "PENALTY_KICK", "RED_CARD")
    ]

    await apply_bot_match_rewards(
        db,
        player_id=uid,
        player_row=player,
        result_str=res_str,
        cards=active_cards,
        club_name=player["club_name"],
        team_rating=my_rating,
        opponent_rating=opp_rating,
        goals_for=state.home_score,
        goals_against=state.away_score,
        points_earned=points_earned,
        lp_change=lp_delta,
        division_win_coins=int(current_div.get("win_coins") or 100),
        run_id=run["id"],
        motm_name=state.live_stats.pick_motm(match_cards[0].name) if match_cards else "Unknown",
        key_events=key_events,
        decided_by=getattr(state, "decided_by", None),
        home_penalties=getattr(state, "home_penalties", None),
        away_penalties=getattr(state, "away_penalties", None),
        dismissals=dismissals_for_rpc(state, match_cards),
        et_fatigue_mult=(
            float(state.et_fatigue_mult)
            if getattr(state, "played_extra_time", False)
            else 1.0
        ),
    )
    await complete_run(
        db,
        run["id"],
        home_score=state.home_score,
        away_score=state.away_score,
        last_minute=int(getattr(state, "minute", 90) or 90),
        competitive_state=snapshot_from_state(state),
    )
    await _notify_participants(
        bot,
        run,
        "Your competitive Bot Battle was interrupted and has been settled from the saved "
        f"checkpoint. Final: {state.home_score}-{state.away_score}"
        + (
            f" ({state.home_penalties}-{state.away_penalties} pens)"
            if getattr(state, "decided_by", None) == "penalties"
            else ""
        )
        + ".",
    )
    logger.info("Competitive bot recovery completed for run %s", run["id"])


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
            rt = run.get("run_type")
            if rt == "league":
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

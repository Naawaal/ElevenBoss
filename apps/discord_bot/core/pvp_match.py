# apps/discord_bot/core/pvp_match.py
"""Ranked PvP shared stadium orchestration (Features 053 & 054) — live human, ghost snapshot, and AI backfill."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import discord

from match_engine import CommentaryEngine, MatchState, stream_match, stream_match_v3

from apps.discord_bot.core.match_runs import (
    ENGINE_NSS_V3,
    abandon_run,
    complete_run,
    generate_sim_seed,
)
from apps.discord_bot.core.squad_fetch import fetch_squad_xi, ordered_cards_to_match_squad
from apps.discord_bot.core.thread_permissions import (
    MATCH_THREAD_ARCHIVE_DELAY_SEC,
    archive_thread_after_delay,
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.embeds.pvp_embeds import opponent_found_embed
from apps.discord_bot.middleware.match_lock import release_match_lock

logger = logging.getLogger(__name__)


def _ticker_helpers():
    from apps.discord_bot.cogs.battle_cog import (
        append_goal_scroll,
        format_ticker_line,
        get_momentum_bar,
        _match_stats_from_state,
    )

    return append_goal_scroll, format_ticker_line, get_momentum_bar, _match_stats_from_state


async def dispatch_matched_pvp(bot: Any, match_meta: dict[str, Any] | str) -> None:
    """Entry from matchmaker / join — run stadium for a claimed PvP run."""
    meta_dict = {"run_id": match_meta} if isinstance(match_meta, str) else (match_meta if isinstance(match_meta, dict) else {})
    run_id = meta_dict.get("run_id")
    if not run_id:
        return
    inflight = getattr(bot, "_pvp_inflight", None)
    if inflight is None:
        bot._pvp_inflight = set()
        inflight = bot._pvp_inflight
    if run_id in inflight:
        return
    inflight.add(run_id)
    try:
        await run_pvp_stadium(bot, meta_dict)
    finally:
        inflight.discard(run_id)


async def run_pvp_stadium(bot: Any, match_meta: dict[str, Any] | str) -> None:
    """
    Executes PvP stadium battle supporting Live Human, Ghost Manager, and Ranked AI opponents.
    """
    append_goal_scroll, format_ticker_line, get_momentum_bar, match_stats = _ticker_helpers()
    db = await get_client()
    meta_dict = {"run_id": match_meta} if isinstance(match_meta, str) else (match_meta if isinstance(match_meta, dict) else {})
    run_id = str(meta_dict.get("run_id") or "")
    if not run_id:
        return

    run_row = (
        await db.table("match_runs").select("*").eq("id", run_id).maybe_single().execute()
    ).data or {}
    snap = dict(run_row.get("squad_snapshot") or meta_dict.get("squad_snapshot") or {})
    opponent_mode = str(run_row.get("opponent_mode") or meta_dict.get("opponent_mode") or snap.get("opponent_mode") or "live")

    home_id_val = meta_dict.get("home_owner_id") or meta_dict.get("home_discord_id") or run_row.get("home_discord_id")
    if home_id_val is None:
        await abandon_run(db, run_id, reason="pvp_missing_home_player")
        return
    home_id = int(home_id_val)

    away_id_val = meta_dict.get("away_owner_id") or meta_dict.get("away_discord_id") or run_row.get("away_discord_id")
    away_id = int(away_id_val) if away_id_val is not None else None

    guild_id = int(meta_dict.get("guild_id") or run_row.get("guild_id") or 0)
    channel_id = int(meta_dict.get("channel_id") or run_row.get("channel_id") or 0)
    sim_seed = int(meta_dict.get("sim_seed") or run_row.get("sim_seed") or generate_sim_seed())
    is_recovery = bool(meta_dict.get("recovery"))

    thread: discord.Thread | None = None
    kicked_off = False

    home_res = await db.table("players").select("*").eq("discord_id", home_id).maybe_single().execute()
    home_p = home_res.data if home_res else None
    if not home_p:
        await abandon_run(db, run_id, reason="pvp_missing_home_player")
        return

    if opponent_mode == "live":
        if away_id is None:
            await abandon_run(db, run_id, reason="pvp_missing_away_player")
            return
        away_res = await db.table("players").select("*").eq("discord_id", away_id).maybe_single().execute()
        away_p = away_res.data if away_res else None
        if not away_p:
            await abandon_run(db, run_id, reason="pvp_missing_away_player")
            return
    elif opponent_mode == "ghost":
        away_name = str(snap.get("away_club_name") or "Ghost Manager")
        away_p = {"discord_id": away_id, "club_name": away_name, "global_division": "Ranked", "global_lp": int(snap.get("away_lp") or 0)}
    else:  # ai_backfill
        away_name = str(snap.get("away_club_name") or "Ranked AI XI")
        away_p = {"discord_id": None, "club_name": away_name, "global_division": "Ranked", "global_lp": 0}

    if run_row and run_row.get("sim_seed") is not None:
        sim_seed = int(run_row["sim_seed"])
    if run_row and run_row.get("channel_id"):
        channel_id = int(run_row["channel_id"])
    if run_row and run_row.get("guild_id"):
        guild_id = int(run_row["guild_id"])

    channel = bot.get_channel(channel_id)
    if channel is None and guild_id:
        guild = bot.get_guild(guild_id)
        if guild:
            channel = guild.get_channel(channel_id)
    if channel is None or not hasattr(channel, "send"):
        logger.error("PvP stadium: channel %s missing for run %s", channel_id, run_id)
        await abandon_run(db, run_id, reason="pvp_channel_missing")
        return

    if is_recovery and run_row.get("thread_id"):
        thread = await _resolve_pvp_thread(bot, int(run_row["thread_id"]), guild_id)
        if thread:
            try:
                await thread.send(
                    embed=discord.Embed(
                        title="♻️ Match recovered",
                        description=f"Bot restarted — replaying Ranked PvP ({opponent_mode.upper()}) from same seed.",
                        color=0xF39C12,
                    )
                )
            except Exception:
                logger.debug("recovery notice failed", exc_info=True)

    if thread is None:
        try:
            found = opponent_found_embed(
                home_name=home_p["club_name"],
                home_div=str(home_p.get("global_division") or "Ranked"),
                home_lp=int(snap.get("home_lp") or home_p.get("global_lp") or 0),
                home_ovr=float(snap.get("home_xi_rating") or 0),
                away_name=away_p["club_name"],
                away_div=str(away_p.get("global_division") or "Ranked"),
                away_lp=int(snap.get("away_lp") or away_p.get("global_lp") or 0),
                away_ovr=float(snap.get("away_xi_rating") or 0),
                opponent_mode=opponent_mode,
                snapshot_age_seconds=snap.get("ghost_snapshot_age_seconds"),
            )

            if opponent_mode == "live" and away_id is not None:
                from apps.discord_bot.embeds.pvp_embeds import rivalry_prematch_field

                riv_line = await rivalry_prematch_field(db, home_id, away_id, home_p, away_p)
                if riv_line:
                    found.add_field(name="🔥 Rivalry", value=riv_line, inline=False)
                ticket_content = f"⚔️ Ranked PvP — <@{home_id}> vs <@{away_id}>"
            elif opponent_mode == "ghost":
                ticket_content = f"👻 Ranked Ghost Match — <@{home_id}> vs **{away_p['club_name']}**"
            else:
                ticket_content = f"🤖 Ranked AI Backfill — <@{home_id}> vs **{away_p['club_name']}**"

            ticket = await channel.send(content=ticket_content, embed=found)
            thread = await channel.create_thread(
                name=f"⚔️ {home_p['club_name']} vs {away_p['club_name']}",
                message=ticket,
                auto_archive_duration=1440,
            )
        except Exception:
            logger.exception("PvP thread create failed run=%s", run_id)
            await abandon_run(db, run_id, reason="pvp_thread_failed")
            try:
                await channel.send(embed=error_embed("Could not open the stadium thread. No energy was charged."))
            except Exception:
                pass
            return

    await db.table("match_runs").update(
        {"thread_id": thread.id, "channel_id": channel_id}
    ).eq("id", run_id).execute()

    try:
        from apps.discord_bot.core.match_runs import squads_from_snapshot

        if snap and snap.get("home_squad") and snap.get("away_squad"):
            home_cards, away_cards = squads_from_snapshot(snap)
            home_card_meta = list(snap.get("home_card_meta") or [])
            away_card_meta = list(snap.get("away_card_meta") or [])
        else:
            _, _, home_active = await fetch_squad_xi(db, home_id)
            home_cards = await ordered_cards_to_match_squad(db, home_active)
            home_card_meta = [{"id": str(c["id"]), "slot": idx + 1} for idx, c in enumerate(home_active)]

            if away_id is not None:
                _, _, away_active = await fetch_squad_xi(db, away_id)
                away_cards = await ordered_cards_to_match_squad(db, away_active)
                away_card_meta = [{"id": str(c["id"]), "slot": idx + 1} for idx, c in enumerate(away_active)]
            else:
                away_cards = []
                away_card_meta = []

        if len(home_cards) != 11 or len(away_cards) != 11:
            await thread.send(embed=error_embed("Starting XI is invalid. Match abandoned — no energy charged."))
            await abandon_run(db, run_id, reason="pvp_xi_invalid")
            return

        home_rating = float(snap.get("home_xi_rating") or (sum(p.overall for p in home_cards) / 11))
        away_rating = float(snap.get("away_xi_rating") or (sum(p.overall for p in away_cards) / 11))

        engine_version = run_row.get("engine_version") or "nss_v2"
        state = MatchState(home_rating=home_rating, away_rating=away_rating)
        state.injuries_enabled = True
        commentary = CommentaryEngine()

        mode_label = "🟢 Live Ranked" if opponent_mode == "live" else ("👻 Ghost Match" if opponent_mode == "ghost" else "🤖 Ranked AI")
        init = discord.Embed(
            title=f"🏟️ Ranked PvP ({mode_label}): {home_p['club_name']} vs {away_p['club_name']}",
            color=0xE67E22,
        )
        init.add_field(
            name="Scoreboard",
            value=f"🏟️ **{home_p['club_name']}** `0 - 0` **{away_p['club_name']}**",
            inline=False,
        )
        init.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
        init.add_field(
            name="Live Commentary",
            value="🟢 **0'** - Kick-off! Match is live.",
            inline=False,
        )

        ticket_mention = f"<@{home_id}>" if opponent_mode != "live" else f"<@{home_id}> <@{away_id}>"
        ticker_msg = await thread.send(
            content=f"{ticket_mention} — watch-only battle in progress.",
            embed=init,
        )
        kicked_off = True

        ticker_history: list[str] = []
        goal_scroll: list[str] = []
        match_rng = random.Random(sim_seed)
        stream = (
            stream_match_v3(
                state,
                home_cards,
                away_cards,
                home_p["club_name"],
                away_p["club_name"],
                sim_seed=sim_seed,
            )
            if engine_version == ENGINE_NSS_V3
            else stream_match(
                state,
                home_cards,
                away_cards,
                home_p["club_name"],
                away_p["club_name"],
                rng=match_rng,
            )
        )

        async for ev in stream:
            variables = {"actor": ev["actor"], "team": ev["team"]}
            comm = commentary.get_commentary(ev["type"], state.context_tags, variables)
            text = comm["text"]
            urgency = comm["urgency"]
            ticker_history.append(format_ticker_line(ev["type"], ev["minute"], text))
            if ev["type"] == "GOAL":
                append_goal_scroll(goal_scroll, ev["minute"], ev["actor"])
            recent = ticker_history[-5:]
            embed = discord.Embed(
                title=f"🏟️ Ranked PvP ({mode_label}): {home_p['club_name']} vs {away_p['club_name']}",
                color=0xE67E22,
            )
            embed.add_field(
                name="Scoreboard",
                value=(
                    f"🏟️ **{home_p['club_name']}** `{ev['score_update']}` "
                    f"**{away_p['club_name']}**"
                ),
                inline=False,
            )
            if goal_scroll:
                embed.add_field(name="Goal Scroll", value="\n".join(goal_scroll), inline=False)
            embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
            embed.add_field(name="Live Commentary", value="\n".join(recent), inline=False)
            await ticker_msg.edit(embed=embed)

            sleep_time = 2.0 if ev["type"] in ["FULL_TIME", "HALF_TIME"] else (3.5 if urgency == "cliffhanger" else (2.5 if urgency == "build_up" else 1.5))
            await asyncio.sleep(sleep_time)

        poss_h, poss_a, shots_h, shots_a = match_stats(state)
        finalize_payload = await _finalize_or_stub(
            db,
            bot,
            run_id=run_id,
            home_id=home_id,
            away_id=away_id or 0,
            home_score=state.home_score,
            away_score=state.away_score,
            home_rating=home_rating,
            away_rating=away_rating,
            home_cards=home_card_meta,
            away_cards=away_card_meta,
            home_p=home_p,
            away_p=away_p,
        )

        result_embed = discord.Embed(
            title=f"🏆 Final Score — {home_p['club_name']} {state.home_score} - {state.away_score} {away_p['club_name']}",
            color=0x3498DB,
        )
        if finalize_payload:
            home_side = finalize_payload.get("home") or {}
            away_side = finalize_payload.get("away") or {}
            if opponent_mode == "live":
                payout_text = (
                    f"**{home_p['club_name']}**: +{int(home_side.get('coins') or 0)} 🪙 | LP {int(home_side.get('lp_delta') or 0):+d}\n"
                    f"**{away_p['club_name']}**: +{int(away_side.get('coins') or 0)} 🪙 | LP {int(away_side.get('lp_delta') or 0):+d}"
                )
            else:
                payout_text = f"**{home_p['club_name']}**: +{int(home_side.get('coins') or 0)} 🪙 | LP {int(home_side.get('lp_delta') or 0):+d}\n*(Opponent: {opponent_mode.replace('_', ' ').title()} — offline manager state unchanged)*"

            result_embed.add_field(name="💰 Payouts & LP", value=payout_text, inline=False)
            riv = finalize_payload.get("rivalry") or {}
            events = riv.get("events") or []
            if events:
                from apps.discord_bot.embeds.pvp_embeds import format_rivalry_events

                result_embed.add_field(name="🔥 Rivalry", value=format_rivalry_events(events), inline=False)
        else:
            result_embed.set_footer(text="Result recorded. Reward finalize pending.")

        await thread.send(content=f"🏁 {ticket_mention}", embed=result_embed)
        if thread.guild:
            asyncio.create_task(
                archive_thread_after_delay(thread, thread.guild, delay=MATCH_THREAD_ARCHIVE_DELAY_SEC)
            )

        if finalize_payload and not finalize_payload.get("rewards_skipped"):
            await _apply_side_xp_fatigue(
                db, bot, finalize_payload, home_cards, away_cards, home_card_meta, away_card_meta, home_p, away_p, state, opponent_mode
            )

    except Exception:
        logger.exception("PvP stadium failed run=%s kicked_off=%s", run_id, kicked_off)
        if not kicked_off:
            await abandon_run(db, run_id, reason="pvp_pre_kickoff_fail")
        else:
            try:
                await abandon_run(db, run_id, reason="pvp_mid_fail")
            except Exception:
                pass
            for uid in ([home_id] if opponent_mode != "live" else [home_id, away_id]):
                if uid:
                    try:
                        await release_match_lock(db, uid)
                    except Exception:
                        pass


async def _resolve_pvp_thread(bot: Any, thread_id: int, guild_id: int) -> discord.Thread | None:
    try:
        t = bot.get_channel(thread_id)
        if isinstance(t, discord.Thread):
            return t
        if guild_id:
            g = bot.get_guild(guild_id)
            if g:
                t = g.get_thread(thread_id)
                if isinstance(t, discord.Thread):
                    return t
    except Exception:
        pass
    return None


async def _finalize_or_stub(
    db: Any,
    bot: Any,
    *,
    run_id: str,
    home_id: int,
    away_id: int,
    home_score: int,
    away_score: int,
    home_rating: float,
    away_rating: float,
    home_cards: list[dict],
    away_cards: list[dict],
    home_p: dict,
    away_p: dict,
) -> dict[str, Any] | None:
    try:
        res = await db.rpc(
            "finalize_pvp_match",
            {
                "p_run_id": run_id,
                "p_home_score": home_score,
                "p_away_score": away_score,
                "p_home_rating": home_rating,
                "p_away_rating": away_rating,
            },
        ).execute()
        data = res.data
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("finalize_pvp_match failed run=%s (%s); run remains completing for recovery", run_id, exc)
        return None


async def _apply_side_xp_fatigue(
    db: Any,
    bot: Any,
    payload: dict[str, Any],
    home_cards: list[Any],
    away_cards: list[Any],
    home_meta: list[dict],
    away_meta: list[dict],
    home_p: dict,
    away_p: dict,
    state: MatchState,
    opponent_mode: str = "live",
) -> None:
    """Post-SQL XP/fatigue using atomic exactly-once RPCs and complete_pvp_run."""
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        return

    try:
        from apps.discord_bot.core.injury_rpc import fetch_bench_ids
        from player_engine.fatigue import match_fatigue_drain, stance_from_tactics_modifier
    except Exception:
        logger.exception("xp/fatigue imports failed")
        return

    sides = [("home", home_cards, home_meta, home_p, state.home_score, state.away_score)]
    if opponent_mode == "live":
        sides.append(("away", away_cards, away_meta, away_p, state.away_score, state.home_score))

    for side, cards, meta, player, gf, ga in sides:
        side_data = payload.get(side) or {}
        history_id = side_data.get("history_id")
        if not history_id:
            continue

        p_id = int(player["discord_id"])
        sub_card_ids = [m["id"] for m in meta if m.get("id")]
        bench_ids = await fetch_bench_ids(db, p_id, sub_card_ids)
        t_mod = getattr(state, "home_tactics_modifier" if side == "home" else "away_tactics_modifier", 1.0)
        stance = stance_from_tactics_modifier(t_mod)
        tier = getattr(state, "intensity_tier", 1)
        # Build per-card drain list matching SQL signature: [{id, drain}, ...]
        starter_drains = [
            {"id": str(meta[i].get("id") or ""), "drain": match_fatigue_drain(getattr(c, "phy", 70), stance=stance, intensity_tier=tier)}
            for i, c in enumerate(cards)
            if i < len(meta) and meta[i].get("id")
        ]

        res_fit = db.rpc(
            "apply_pvp_post_match_fitness_once",
            {
                "p_history_id": history_id,
                "p_run_id": run_id,
                "p_owner_id": p_id,
                "p_starter_drains": starter_drains,
                "p_bench_ids": bench_ids,
                "p_recorded_injuries": side_data.get("recorded_injuries") or [],
            },
        )
        if hasattr(res_fit, "execute"):
            await res_fit.execute()
        else:
            await res_fit

        res_xp = db.rpc(
            "apply_pvp_match_xp_once",
            {
                "p_history_id": history_id,
                "p_run_id": run_id,
                "p_owner_id": p_id,
                "p_result_str": side_data.get("result") or "draw",
                "p_cards": meta,
                "p_team_rating": float(side_data.get("rating") or 80.0),
            },
        )
        if hasattr(res_xp, "execute"):
            await res_xp.execute()
        else:
            await res_xp


async def recover_active_pvp_runs(bot: Any, db: Any) -> int:
    """Recover interrupted PvP match runs by redispatching stadium tasks."""
    builder = db.table("match_runs").select("*").eq("status", "streaming").eq("run_type", "pvp")
    res = await (builder.execute() if hasattr(builder, "execute") else builder)
    runs = getattr(res, "data", []) or []
    count = 0
    for run in runs:
        try:
            asyncio.create_task(dispatch_matched_pvp(bot, run["id"]))
            count += 1
        except Exception:
            logger.exception("Failed to recover pvp run %s", run.get("id"))
    return count


async def retry_completing_pvp_runs(db: Any, bot: Any = None) -> int:
    """Retry completion for stuck completing PvP match runs."""
    builder = db.table("match_runs").select("*").eq("status", "completing").eq("run_type", "pvp")
    res = await (builder.execute() if hasattr(builder, "execute") else builder)
    runs = getattr(res, "data", []) or []
    count = 0
    for run in runs:
        try:
            # complete_pvp_run only takes p_run_id; scores already stored by finalize_pvp_match
            rpc_res = db.rpc("complete_pvp_run", {"p_run_id": run["id"]})
            if hasattr(rpc_res, "execute"):
                await rpc_res.execute()
            else:
                await rpc_res
            count += 1
        except Exception:
            logger.exception("Failed to retry completing pvp run %s", run.get("id"))
    return count

# apps/discord_bot/core/pvp_match.py
"""Ranked PvP shared stadium orchestration (Feature 053) — watch-only dual-human live match."""
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

# Reuse ticker helpers from battle_cog without circular import at module load
def _ticker_helpers():
    from apps.discord_bot.cogs.battle_cog import (
        append_goal_scroll,
        format_ticker_line,
        get_momentum_bar,
        _match_stats_from_state,
    )

    return append_goal_scroll, format_ticker_line, get_momentum_bar, _match_stats_from_state


async def dispatch_matched_pvp(bot: Any, match_meta: dict[str, Any]) -> None:
    """Entry from matchmaker / join — run one shared stadium for a claimed PvP run."""
    run_id = match_meta.get("run_id")
    if not run_id:
        return
    # Dedup in-flight
    inflight = getattr(bot, "_pvp_inflight", None)
    if inflight is None:
        bot._pvp_inflight = set()
        inflight = bot._pvp_inflight
    if run_id in inflight:
        return
    inflight.add(run_id)
    try:
        await run_pvp_stadium(bot, match_meta)
    finally:
        inflight.discard(run_id)


async def run_pvp_stadium(bot: Any, match_meta: dict[str, Any]) -> None:
    """
    Locks are already held by try_match_pvp_queue.
    On thread/setup failure before kickoff: abandon run (releases locks), no energy/rewards.
    Recovery path reuses sim_seed + existing thread when present.
    """
    append_goal_scroll, format_ticker_line, get_momentum_bar, match_stats = _ticker_helpers()
    db = await get_client()
    run_id = str(match_meta["run_id"])
    home_id = int(match_meta["home_owner_id"])
    away_id = int(match_meta["away_owner_id"])
    guild_id = int(match_meta.get("guild_id") or 0)
    channel_id = int(match_meta.get("channel_id") or 0)
    sim_seed = int(match_meta.get("sim_seed") or generate_sim_seed())
    is_recovery = bool(match_meta.get("recovery"))

    thread: discord.Thread | None = None
    kicked_off = False

    home_res = await db.table("players").select("*").eq("discord_id", home_id).maybe_single().execute()
    away_res = await db.table("players").select("*").eq("discord_id", away_id).maybe_single().execute()
    home_p = home_res.data if home_res else None
    away_p = away_res.data if away_res else None
    if not home_p or not away_p:
        await abandon_run(db, run_id, reason="pvp_missing_player")
        return

    run_row = (
        await db.table("match_runs").select("*").eq("id", run_id).maybe_single().execute()
    ).data
    snap = dict((run_row or {}).get("squad_snapshot") or match_meta.get("squad_snapshot") or {})
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

    # Recovery: reuse existing stadium thread when possible
    if is_recovery and (run_row or {}).get("thread_id"):
        thread = await _resolve_pvp_thread(bot, int(run_row["thread_id"]), guild_id)
        if thread:
            try:
                await thread.send(
                    embed=discord.Embed(
                        title="♻️ Match recovered",
                        description="Bot restarted — replaying this Ranked PvP from the same seed. No double rewards.",
                        color=0xF39C12,
                    )
                )
            except Exception:
                logger.debug("recovery notice failed", exc_info=True)

    if thread is None:
        try:
            from apps.discord_bot.embeds.pvp_embeds import rivalry_prematch_field

            found = opponent_found_embed(
                home_name=home_p["club_name"],
                home_div=str(match_meta.get("home_div") or home_p.get("global_division") or "—"),
                home_lp=int(home_p.get("global_lp") or 0),
                home_ovr=float(snap.get("home_xi_rating") or 0),
                away_name=away_p["club_name"],
                away_div=str(match_meta.get("away_div") or away_p.get("global_division") or "—"),
                away_lp=int(away_p.get("global_lp") or 0),
                away_ovr=float(snap.get("away_xi_rating") or 0),
            )
            if snap:
                found = opponent_found_embed(
                    home_name=home_p["club_name"],
                    home_div="Ranked",
                    home_lp=int(snap.get("home_lp") or home_p.get("global_lp") or 0),
                    home_ovr=float(snap.get("home_xi_rating") or 0),
                    away_name=away_p["club_name"],
                    away_div="Ranked",
                    away_lp=int(snap.get("away_lp") or away_p.get("global_lp") or 0),
                    away_ovr=float(snap.get("away_xi_rating") or 0),
                )
            riv_line = await rivalry_prematch_field(db, home_id, away_id, home_p, away_p)
            if riv_line:
                found.add_field(name="🔥 Rivalry", value=riv_line, inline=False)
            ticket = await channel.send(
                content=f"⚔️ Ranked PvP — <@{home_id}> vs <@{away_id}>",
                embed=found,
            )
            thread = await channel.create_thread(
                name=f"⚔️ {home_p['club_name']} vs {away_p['club_name']} – Ranked",
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
        else:
            _, _, home_active = await fetch_squad_xi(db, home_id)
            _, _, away_active = await fetch_squad_xi(db, away_id)
            home_cards = await ordered_cards_to_match_squad(db, home_active)
            away_cards = await ordered_cards_to_match_squad(db, away_active)

        if len(home_cards) != 11 or len(away_cards) != 11:
            await thread.send(embed=error_embed("A manager no longer has a valid XI. Match abandoned — no energy charged."))
            await abandon_run(db, run_id, reason="pvp_xi_invalid")
            return

        home_rating = float(snap.get("home_rating") or (sum(p.overall for p in home_cards) / 11))
        away_rating = float(snap.get("away_rating") or (sum(p.overall for p in away_cards) / 11))

        engine_version = (run_row or {}).get("engine_version") or "nss_v2"
        state = MatchState(home_rating=home_rating, away_rating=away_rating)
        state.injuries_enabled = True
        commentary = CommentaryEngine()

        init = discord.Embed(
            title=f"🏟️ Ranked PvP: {home_p['club_name']} vs {away_p['club_name']}",
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
            value="🟢 **0'** - Kick-off! Ranked PvP is live.",
            inline=False,
        )
        ticker_msg = await thread.send(
            content=f"<@{home_id}> <@{away_id}> — watch-only (no mid-match tactics).",
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
                title=f"🏟️ Ranked PvP: {home_p['club_name']} vs {away_p['club_name']}",
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

            if ev["type"] in ["FULL_TIME", "HALF_TIME"]:
                sleep_time = 2.0
            elif urgency == "cliffhanger":
                sleep_time = 3.5
            elif urgency == "build_up":
                sleep_time = 2.5
            else:
                sleep_time = 1.5
            await asyncio.sleep(sleep_time)

        poss_h, poss_a, shots_h, shots_a = match_stats(state)
        finalize_payload = await _finalize_or_stub(
            db,
            bot,
            run_id=run_id,
            home_id=home_id,
            away_id=away_id,
            home_score=state.home_score,
            away_score=state.away_score,
            home_rating=home_rating,
            away_rating=away_rating,
            home_cards=home_active,
            away_cards=away_active,
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
            result_embed.add_field(
                name=f"💰 Payouts & LP",
                value=(
                    f"**{home_p['club_name']}**: +{int(home_side.get('coins') or 0)} 🪙 | "
                    f"LP {int(home_side.get('lp_delta') or 0):+d}\n"
                    f"**{away_p['club_name']}**: +{int(away_side.get('coins') or 0)} 🪙 | "
                    f"LP {int(away_side.get('lp_delta') or 0):+d}"
                ),
                inline=False,
            )
            if finalize_payload.get("rewards_skipped"):
                result_embed.set_footer(text="Rewards disabled (pvp_rewards_enabled=false) — result recorded.")
            riv = finalize_payload.get("rivalry") or {}
            events = riv.get("events") or []
            if events:
                from apps.discord_bot.embeds.pvp_embeds import format_rivalry_events

                result_embed.add_field(
                    name="🔥 Rivalry",
                    value=format_rivalry_events(events),
                    inline=False,
                )
            asyncio.create_task(
                _maybe_send_rivalry_dms(bot, db, home_id, away_id, home_p, away_p, riv, state)
            )
        else:
            result_embed.set_footer(text="Result recorded. Reward finalize pending / stub.")

        await thread.send(content=f"🏁 <@{home_id}> <@{away_id}>", embed=result_embed)
        try:
            await thread.edit(
                name=(
                    f"⚔️ {home_p['club_name']} {state.home_score}-{state.away_score} "
                    f"{away_p['club_name']} – Ranked"
                )
            )
        except Exception:
            logger.debug("rename pvp thread failed", exc_info=True)

        if thread.guild:
            asyncio.create_task(
                archive_thread_after_delay(
                    thread, thread.guild, delay=MATCH_THREAD_ARCHIVE_DELAY_SEC
                )
            )

        # Apply XP/fatigue best-effort after SQL finalize (history rows exist)
        if finalize_payload and not finalize_payload.get("rewards_skipped"):
            await _apply_side_xp_fatigue(
                db, bot, finalize_payload, home_cards, away_cards, home_p, away_p, state
            )

    except Exception:
        logger.exception("PvP stadium failed run=%s kicked_off=%s", run_id, kicked_off)
        if not kicked_off:
            await abandon_run(db, run_id, reason="pvp_pre_kickoff_fail")
        else:
            try:
                await abandon_run(db, run_id, reason="pvp_mid_fail")
            except Exception:
                logger.exception("abandon after mid-fail")
            for uid in (home_id, away_id):
                try:
                    await release_match_lock(db, uid)
                except Exception:
                    pass
        if thread:
            try:
                await thread.send(embed=error_embed("Ranked match failed. Ops will investigate."))
            except Exception:
                pass


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
    home_cards: list[dict],
    away_cards: list[dict],
    home_p: dict,
    away_p: dict,
    state: MatchState,
) -> None:
    """Post-SQL XP/fatigue using atomic exactly-once RPCs and complete_pvp_run."""
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        return

    try:
        from apps.discord_bot.core.injury_rpc import fetch_bench_ids
        from player_engine.fatigue import match_fatigue_drain
    except Exception:
        logger.exception("xp/fatigue imports failed")
        return

    for side, cards, player, gf, ga in (
        ("home", home_cards, home_p, state.home_score, state.away_score),
        ("away", away_cards, away_p, state.away_score, state.home_score),
    ):
        side_data = payload.get(side) or {}
        history_id = side_data.get("history_id")
        if not history_id:
            continue
        pid = int(player["discord_id"])
        res_str = "win" if gf > ga else ("draw" if gf == ga else "loss")
        cards_json = [
            {
                "id": str(c.get("id", "")),
                "level": int(c.get("level", 1)),
                "date_of_birth": str(c.get("date_of_birth", "2000-01-01")),
            }
            for c in cards
        ]
        try:
            await db.rpc(
                "apply_pvp_match_xp_once",
                {
                    "p_history_id": str(history_id),
                    "p_run_id": run_id,
                    "p_owner_id": pid,
                    "p_result_str": res_str,
                    "p_cards": cards_json,
                    "p_team_rating": float(side_data.get("rating") or 0),
                },
            ).execute()
        except Exception:
            logger.exception("pvp XP apply failed side=%s run=%s", side, run_id)

        try:
            starter_ids = [str(getattr(c, "id", c.get("id") if isinstance(c, dict) else "")) for c in cards if getattr(c, "id", c.get("id") if isinstance(c, dict) else "")]
            bench_ids = await fetch_bench_ids(db, pid, starter_ids)
            tier = int(player.get("intensity_tier") or 1)
            drains = [
                {
                    "id": str(getattr(c, "id", c.get("id") if isinstance(c, dict) else "")),
                    "drain": match_fatigue_drain(int(getattr(c, "phy", 70) if not isinstance(c, dict) else c.get("phy", 70)), intensity_tier=tier),
                }
                for c in cards
            ]
            await db.rpc(
                "apply_pvp_post_match_fitness_once",
                {
                    "p_history_id": str(history_id),
                    "p_run_id": run_id,
                    "p_owner_id": pid,
                    "p_starter_drains": drains,
                    "p_bench_ids": bench_ids,
                    "p_recorded_injuries": [],
                },
            ).execute()
        except Exception:
            logger.exception("pvp fatigue apply failed side=%s run=%s", side, run_id)

    try:
        await db.rpc("complete_pvp_run", {"p_run_id": run_id}).execute()
    except Exception:
        logger.exception("complete_pvp_run failed run=%s", run_id)


async def retry_completing_pvp_runs(db: Any, bot: Any = None) -> None:
    """Scheduler recovery pass retrying progression for any runs stuck in 'completing'."""
    try:
        res = await db.table("match_runs").select("*").eq("run_type", "pvp").eq("status", "completing").execute()
        runs = res.data or []
        for run in runs:
            run_id = str(run["id"])
            home_id = int(run["home_discord_id"])
            away_id = int(run["away_discord_id"])
            snap = dict(run.get("squad_snapshot") or {})
            home_p_res = await db.table("players").select("*").eq("discord_id", home_id).maybe_single().execute()
            away_p_res = await db.table("players").select("*").eq("discord_id", away_id).maybe_single().execute()
            if not home_p_res or not away_p_res:
                continue
            home_p = home_p_res.data
            away_p = away_p_res.data

            from apps.discord_bot.core.match_runs import squads_from_snapshot
            home_cards, away_cards = squads_from_snapshot(snap) if snap.get("home_squad") else ([], [])
            state = MatchState(home_rating=float(snap.get("home_rating") or 80), away_rating=float(snap.get("away_rating") or 80))
            state.home_score = int(run.get("home_score") or 0)
            state.away_score = int(run.get("away_score") or 0)

            hist_res = await db.table("match_history").select("*").eq("run_id", run_id).execute()
            hists = hist_res.data or []
            home_h = next((h for h in hists if int(h["player_id"]) == home_id), None)
            away_h = next((h for h in hists if int(h["player_id"]) == away_id), None)
            if not home_h or not away_h:
                continue

            payload = {
                "run_id": run_id,
                "home": {"history_id": home_h["id"], "rating": snap.get("home_rating")},
                "away": {"history_id": away_h["id"], "rating": snap.get("away_rating")},
            }
            await _apply_side_xp_fatigue(db, bot, payload, home_cards, away_cards, home_p, away_p, state)
    except Exception:
        logger.exception("retry_completing_pvp_runs failed")


async def _resolve_pvp_thread(bot: Any, thread_id: int, guild_id: int) -> discord.Thread | None:
    guild = bot.get_guild(guild_id) if guild_id else None
    if guild:
        t = guild.get_thread(thread_id)
        if t:
            return t
    try:
        ch = await bot.fetch_channel(thread_id)
        return ch if isinstance(ch, discord.Thread) else None
    except Exception:
        return None


async def _pvp_rewards_applied(db: Any, run: dict[str, Any]) -> bool:
    run_id = run.get("id")
    if not run_id:
        return False
    from apps.discord_bot.core.match_runs import fetch_match_reward_row

    for key in ("home_discord_id", "away_discord_id", "active_discord_id"):
        uid = run.get(key)
        if not uid:
            continue
        row = await fetch_match_reward_row(db, int(uid), run_id=run_id)
        if row:
            return True
    return False


async def recover_active_pvp_runs(bot: Any, db: Any) -> int:
    """Resume or complete-once interrupted Ranked PvP runs (US7)."""
    res = (
        await db.table("match_runs")
        .select("*")
        .eq("run_type", "pvp")
        .eq("status", "streaming")
        .execute()
    )
    recovered = 0
    for run in res.data or []:
        try:
            if await _pvp_rewards_applied(db, run):
                await complete_run(
                    db,
                    run["id"],
                    home_score=int(run.get("home_score") or 0),
                    away_score=int(run.get("away_score") or 0),
                )
                recovered += 1
                logger.info("pvp_recovery completed_after_rewards run=%s", run["id"])
                continue
            meta = {
                "run_id": run["id"],
                "home_owner_id": run.get("home_discord_id"),
                "away_owner_id": run.get("away_discord_id"),
                "guild_id": run.get("guild_id"),
                "channel_id": run.get("channel_id"),
                "sim_seed": run.get("sim_seed"),
                "squad_snapshot": run.get("squad_snapshot"),
                "recovery": True,
            }
            if not meta["home_owner_id"] or not meta["away_owner_id"]:
                await abandon_run(db, run["id"], reason="pvp_recovery_missing_owners")
                recovered += 1
                continue
            asyncio.create_task(dispatch_matched_pvp(bot, meta))
            recovered += 1
            logger.info("pvp_recovery redispatched run=%s seed=%s", run["id"], run.get("sim_seed"))
        except Exception:
            logger.exception("pvp_recovery failed run=%s", run.get("id"))
    return recovered




async def _maybe_send_rivalry_dms(
    bot: Any,
    db: Any,
    home_id: int,
    away_id: int,
    home_p: dict,
    away_p: dict,
    riv: dict[str, Any],
    state: MatchState,
) -> None:
    """Result-only rivalry DMs — never presence/login alerts (US6). Rate-limited lightly."""
    events = riv.get("events") or []
    if not events:
        return
    from apps.discord_bot.embeds.pvp_embeds import format_rivalry_events

    body = (
        f"Ranked PvP vs rival finished **{state.home_score}–{state.away_score}**.\n"
        f"{format_rivalry_events(events)}"
    )
    for uid, player in ((home_id, home_p), (away_id, away_p)):
        if player.get("pvp_rivalry_dms") is False:
            continue
        # ponytail: process-local 5m mute; upgrade to Redis if multi-instance
        bucket = getattr(bot, "_pvp_rivalry_dm_at", None)
        if bucket is None:
            bot._pvp_rivalry_dm_at = {}
            bucket = bot._pvp_rivalry_dm_at
        import time

        now = time.monotonic()
        if now - float(bucket.get(uid, 0)) < 300:
            continue
        bucket[uid] = now
        try:
            user = await bot.fetch_user(uid)
            await user.send(f"🔥 Rivalry update\n{body}")
        except Exception:
            logger.debug("rivalry DM failed uid=%s", uid, exc_info=True)

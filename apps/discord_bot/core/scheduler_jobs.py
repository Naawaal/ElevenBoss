# apps/discord_bot/core/scheduler_jobs.py
from __future__ import annotations
import logging
import discord
from discord.ext import commands
from leagues import LeagueEntry, compute_promotions_relegations
from apps.discord_bot.db.client import get_client

logger = logging.getLogger(__name__)

DIVISIONS = ["Grassroots", "Amateur", "Semi-Pro", "Professional", "Elite", "Legendary"]

async def season_aging_job(bot: commands.Bot) -> None:
    """Monday 00:00 UTC — refresh ages, apply decline, retire veterans (Phase A)."""
    logger.info("Executing season aging batch...")
    try:
        db = await get_client()
        res = await db.rpc("process_season_aging").execute()
        summary = res.data or {}
        logger.info(
            "Season aging complete: declined=%s retired=%s warned=%s",
            summary.get("declined_cards", 0),
            summary.get("retired_cards", 0),
            summary.get("warned_cards", 0),
        )
    except Exception:
        logger.exception("Season aging job failed.")


async def youth_intake_job(bot: commands.Bot) -> None:
    """Monday 00:00 UTC — flat L1 youth intake for all human managers (Phase B)."""
    logger.info("Executing weekly youth intake...")
    try:
        from apps.discord_bot.tasks.youth_intake_notifier import run_season_youth_intake

        await run_season_youth_intake(bot)
    except Exception:
        logger.exception("Youth intake job failed.")


async def regen_pool_job(bot: commands.Bot) -> None:
    """Monday 00:00 UTC — list retired 75+ OVR players on scouting market (Phase D)."""
    logger.info("Executing regen scouting pool spawn...")
    try:
        from apps.discord_bot.tasks.regen_pool_job import spawn_regens_from_recent_retirements

        await spawn_regens_from_recent_retirements(bot)
    except Exception:
        logger.exception("Regen pool job failed.")


async def daily_recovery_job(bot: commands.Bot) -> None:
    """Daily 00:05 UTC — fatigue recovery + hospital discharges / untreated clocks."""
    logger.info("Executing daily fatigue/injury recovery...")
    try:
        db = await get_client()
        res = await db.rpc("process_daily_recovery").execute()
        summary = res.data or {}
        logger.info("Daily recovery complete: %s", summary)
    except Exception:
        logger.exception("Daily recovery job failed.")


async def academy_growth_job(bot: commands.Bot) -> None:
    """Daily 00:10 UTC — academy passive growth + age-out promote/release."""
    logger.info("Executing daily academy growth...")
    try:
        from apps.discord_bot.tasks.academy_growth_job import run_daily_academy_growth

        await run_daily_academy_growth(bot)
    except Exception:
        logger.exception("Academy growth job failed.")


async def transfer_listing_expiry_job(bot: commands.Bot) -> None:
    """Hourly — release cards from expired manager-to-manager listings."""
    try:
        from apps.discord_bot.tasks.transfer_listing_expiry_job import expire_stale_transfer_listings

        await expire_stale_transfer_listings()
    except Exception:
        logger.exception("Transfer-listing expiry job failed.")


async def weekly_payroll_job(bot: commands.Bot) -> None:
    """Monday 00:05 UTC — Starting XI wage payroll when wages_payroll_enabled."""
    logger.info("Executing weekly payroll batch...")
    try:
        from apps.discord_bot.tasks.weekly_payroll_job import run_weekly_payroll

        await run_weekly_payroll()
    except Exception:
        logger.exception("Weekly payroll job failed.")


async def weekly_league_reset_job(bot: commands.Bot) -> None:
    """
    APScheduler cron job (Monday 00:00 UTC) to:
    1. Group players by division.
    2. Rank them and calculate promotions & relegations.
    3. Update divisions in database.
    4. Reset all league points and goal differences to 0.
    5. Dispatch DMs to promoted/relegated managers.
    """
    logger.info("Executing weekly league promotion and relegation reset...")
    try:
        db = await get_client()
        
        # 1. Fetch all players
        players_res = await db.table("players").select(
            "discord_id, division, league_points, goal_difference, username, is_ai, best_weekly_pts"
        ).execute()
        all_players = players_res.data or []
        if not all_players:
            logger.info("No players found to reset.")
            return

        # 2. Group by division
        by_division: dict[str, list[dict]] = {div: [] for div in DIVISIONS}
        for p in all_players:
            div = p.get("division", "Grassroots")
            if div in by_division:
                by_division[div].append(p)
            else:
                by_division["Grassroots"].append(p)

        # We will collect all database update operations
        promotions: list[int] = []
        relegations: list[int] = []

        # 3. Compute promotions & relegations per division
        for div_idx, div_name in enumerate(DIVISIONS):
            div_players = by_division[div_name]
            if not div_players:
                continue

            # Convert to LeagueEntry models
            entries = [
                LeagueEntry(
                    discord_id=p["discord_id"],
                    league_points=p["league_points"],
                    goal_difference=p["goal_difference"]
                )
                for p in div_players
            ]

            res = compute_promotions_relegations(entries)

            # Promoted: move up if not in highest division
            if div_idx < len(DIVISIONS) - 1:
                promotions.extend(res.promoted_ids)
            
            # Relegated: move down if not in lowest division
            if div_idx > 0:
                relegated_ids_valid = [pid for pid in res.relegated_ids]
                relegations.extend(relegated_ids_valid)

        # 3b. Snapshot best weekly stats (in-memory points; before reset)
        for div_name in DIVISIONS:
            div_humans = sorted(
                [p for p in by_division[div_name] if not p.get("is_ai")],
                key=lambda p: (-p["league_points"], -p["goal_difference"]),
            )
            for rank, p in enumerate(div_humans, 1):
                pts = int(p.get("league_points", 0))
                best = int(p.get("best_weekly_pts") or 0)
                if pts > best:
                    await db.table("players").update({
                        "best_weekly_pts": pts,
                        "best_weekly_rank": rank,
                    }).eq("discord_id", p["discord_id"]).execute()

        # 4. Apply database division updates
        promo_new_div: dict[int, str] = {}
        for pid in promotions:
            p_data = next((x for x in all_players if x["discord_id"] == pid), None)
            if p_data:
                old_div = p_data["division"]
                new_div = DIVISIONS[min(DIVISIONS.index(old_div) + 1, len(DIVISIONS) - 1)]
                await db.table("players").update({"division": new_div}).eq("discord_id", pid).execute()
                promo_new_div[pid] = new_div

        releg_new_div: dict[int, str] = {}
        for pid in relegations:
            p_data = next((x for x in all_players if x["discord_id"] == pid), None)
            if p_data:
                old_div = p_data["division"]
                new_div = DIVISIONS[max(DIVISIONS.index(old_div) - 1, 0)]
                await db.table("players").update({"division": new_div}).eq("discord_id", pid).execute()
                releg_new_div[pid] = new_div

        # 4a. Drift-proof intensity_tier from settled division (016)
        from player_engine import intensity_tier_for_division

        for div_name in DIVISIONS:
            tier = intensity_tier_for_division(div_name)
            await db.table("players").update({"intensity_tier": tier}).eq(
                "division", div_name
            ).execute()

        # 4b. Weekly summary DMs
        for div_name in DIVISIONS:
            div_humans = sorted(
                [p for p in by_division[div_name] if not p.get("is_ai")],
                key=lambda p: (-p["league_points"], -p["goal_difference"]),
            )
            for rank, p in enumerate(div_humans, 1):
                pts = int(p.get("league_points", 0))
                pid = p["discord_id"]
                if pts <= 0 and pid not in promo_new_div and pid not in releg_new_div:
                    continue
                lines = [f"📊 **Weekly Division Rank** — **#{rank}** in **{div_name}** with **{pts}** pts."]
                if pid in promo_new_div:
                    lines.append(f"🚀 Promoted to **{promo_new_div[pid]}**!")
                elif pid in releg_new_div:
                    lines.append(f"📉 Relegated to **{releg_new_div[pid]}**.")
                lines.append("Fresh week starts now — `/leaderboard`")
                await _send_dm(bot, pid, "\n".join(lines))

        # 5. Reset all points and goal differences to 0
        await db.table("players").update({"league_points": 0, "goal_difference": 0}).neq("discord_id", 0).execute()
        logger.info("Weekly league reset completed successfully.")

    except Exception as e:
        logger.error(f"Failed to execute weekly league reset: {e}", exc_info=True)

async def _send_dm(bot: commands.Bot, user_id: int, message: str) -> None:
    """Helper to dispatch DMs to users safely."""
    try:
        user = bot.get_user(user_id)
        if not user:
            user = await bot.fetch_user(user_id)
        if user:
            await user.send(message)
    except discord.Forbidden:
        # User has DMs disabled
        pass
    except Exception as e:
        logger.warning(f"Failed to send DM to user {user_id}: {e}")

async def auto_sim_expired_fixtures_job(bot: commands.Bot) -> None:
    """APScheduler interval job — legacy pacing seasons only (NULL treated as legacy)."""
    logger.info("Executing auto simulation check for expired fixtures...")
    try:
        db = await get_client()
        seasons_res = await (
            db.table("league_seasons")
            .select("id, pacing_mode")
            .eq("status", "active")
            .execute()
        )
        seasons = seasons_res.data or []
        for s in seasons:
            mode = s.get("pacing_mode") or "legacy"
            if mode != "legacy":
                continue
            from apps.discord_bot.cogs.league_cog import auto_sim_expired_fixtures
            count = await auto_sim_expired_fixtures(db, s["id"], bot)
            if count > 0:
                logger.info(f"Auto-simulated {count} fixtures for season {s['id']}")
    except Exception as e:
        logger.error(f"Failed to execute auto simulation job: {e}", exc_info=True)


async def dynamics_daily_tick_job(bot: commands.Bot) -> None:
    """Deprecated — folded into ``league_state_machine_job`` (021). Kept for import safety."""
    await league_state_machine_job(bot)


async def league_state_machine_job(bot: commands.Bot) -> None:
    """Cron 00:05 UTC — Dynamics ticks + League Automation lifecycle (021)."""
    from apps.discord_bot.core.league_automation import run_league_state_machine

    await run_league_state_machine(bot)


async def league_matchday_reminder_job(bot: commands.Bot) -> None:
    """DM managers ~6h before matchday window closes (US-26, US-29f dedup)."""
    from datetime import datetime, timezone, timedelta
    try:
        db = await get_client()
        now = datetime.now(timezone.utc)
        warn_by = now + timedelta(hours=6)
        seasons_res = await db.table("league_seasons").select("id, current_matchday, league_id").eq("status", "active").execute()
        for season in seasons_res.data or []:
            fix_res = await db.table("league_fixtures").select("window_end, home_team_id, away_team_id").eq(
                "season_id", season["id"]
            ).eq("matchday", season["current_matchday"]).eq("is_played", False).limit(1).execute()
            if not fix_res.data:
                continue
            window_end = datetime.fromisoformat(fix_res.data[0]["window_end"].replace("Z", "+00:00"))
            if not (now < window_end <= warn_by):
                continue
            league_res = await db.table("leagues").select("guild_id").eq("id", season["league_id"]).maybe_single().execute()
            if not league_res or not league_res.data:
                continue
            parts_res = await db.table("league_participants").select("player_id, players(is_ai)").eq("season_id", season["id"]).execute()
            for p in parts_res.data or []:
                pl = p.get("players") or {}
                if pl.get("is_ai"):
                    continue
                pid = p["player_id"]
                existing = await db.table("league_matchday_reminders").select("player_id").eq(
                    "season_id", season["id"]
                ).eq("matchday", season["current_matchday"]).eq("player_id", pid).maybe_single().execute()
                if existing and existing.data:
                    continue
                await _send_dm(
                    bot, pid,
                    f"⏰ **Matchday {season['current_matchday']}** closes in under 6 hours! "
                    f"Play your fixture via `/league hub` before auto-sim kicks in.",
                )
                await db.table("league_matchday_reminders").insert({
                    "season_id": season["id"],
                    "matchday": season["current_matchday"],
                    "player_id": pid,
                }).execute()
    except Exception as e:
        logger.error("league_matchday_reminder_job failed: %s", e, exc_info=True)

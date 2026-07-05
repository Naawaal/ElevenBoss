# apps/discord_bot/core/scheduler_jobs.py
from __future__ import annotations
import logging
import discord
from discord.ext import commands
from leagues import LeagueEntry, compute_promotions_relegations
from apps.discord_bot.db.client import get_client

logger = logging.getLogger(__name__)

DIVISIONS = ["Grassroots", "Amateur", "Semi-Pro", "Professional", "Elite", "Legendary"]

async def energy_regen_job() -> None:
    """APScheduler interval job to regenerate player energy by +2 every 5 minutes."""
    logger.info("Executing passive energy regeneration tick...")
    try:
        db = await get_client()
        await db.rpc("regen_energy_tick", {}).execute()
        logger.info("Energy regeneration tick complete.")
    except Exception as e:
        logger.error(f"Failed to execute energy regeneration tick: {e}", exc_info=True)

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
        players_res = await db.table("players").select("discord_id, division, league_points, goal_difference, username").execute()
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

        # 4. Apply database division updates
        # Update promoted players
        for pid in promotions:
            # Find old division index
            p_data = next((x for x in all_players if x["discord_id"] == pid), None)
            if p_data:
                old_div = p_data["division"]
                new_div = DIVISIONS[min(DIVISIONS.index(old_div) + 1, len(DIVISIONS) - 1)]
                await db.table("players").update({"division": new_div}).eq("discord_id", pid).execute()
                await _send_dm(bot, pid, f"🚀 **CONGRATULATIONS!** You have been promoted to the **{new_div}** division in ElevenBoss! Check `/profile` for details.")

        # Update relegated players
        for pid in relegations:
            p_data = next((x for x in all_players if x["discord_id"] == pid), None)
            if p_data:
                old_div = p_data["division"]
                new_div = DIVISIONS[max(DIVISIONS.index(old_div) - 1, 0)]
                await db.table("players").update({"division": new_div}).eq("discord_id", pid).execute()
                await _send_dm(bot, pid, f"📉 **NOTICE**: You have been relegated to the **{new_div}** division in ElevenBoss. Build up your squad and push for promotion next week!")

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
    """APScheduler interval job to auto-simulate expired league fixtures."""
    logger.info("Executing auto simulation check for expired fixtures...")
    try:
        db = await get_client()
        # Find all active seasons
        seasons_res = await db.table("league_seasons").select("id").eq("status", "active").execute()
        seasons = seasons_res.data or []
        for s in seasons:
            from apps.discord_bot.cogs.league_cog import auto_sim_expired_fixtures
            count = await auto_sim_expired_fixtures(db, s["id"], bot)
            if count > 0:
                logger.info(f"Auto-simulated {count} fixtures for season {s['id']}")
    except Exception as e:
        logger.error(f"Failed to execute auto simulation job: {e}", exc_info=True)

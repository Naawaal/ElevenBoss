# apps/discord_bot/main.py
from __future__ import annotations
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.discord_bot.core.thread_manager import ThreadManager
from apps.discord_bot.core.scheduler_jobs import weekly_league_reset_job, auto_sim_expired_fixtures_job, league_matchday_reminder_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()

# Set up bot intents (no Message Content Intent required)
intents = discord.Intents.default()
intents.members = True  # Required to resolve user metadata / DM

class ElevenBossBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.thread_manager: ThreadManager = ThreadManager(self)
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone="UTC")
        self.cogs_list = [
            "apps.discord_bot.cogs.onboarding_cog",
            "apps.discord_bot.cogs.squad_cog",
            "apps.discord_bot.cogs.player_cog",
            "apps.discord_bot.cogs.profile_cog",
            "apps.discord_bot.cogs.economy_cog",
            "apps.discord_bot.cogs.store_cog",
            "apps.discord_bot.cogs.development_cog",
            "apps.discord_bot.cogs.marketplace_cog",
            "apps.discord_bot.cogs.battle_cog",
            "apps.discord_bot.cogs.admin_cog",
            "apps.discord_bot.cogs.league_cog",
            "apps.discord_bot.cogs.leaderboard_cog",
        ]

    async def setup_hook(self) -> None:
        # Load cogs
        for cog in self.cogs_list:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}", exc_info=True)

        from apps.discord_bot.views.level_reward_claim import ClaimAllLevelRewardsView
        self.add_view(ClaimAllLevelRewardsView())

        @self.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction,
            error: app_commands.AppCommandError,
        ) -> None:
            original = getattr(error, "original", error)
            cmd_name = interaction.command.qualified_name if interaction.command else "unknown"
            user_id = interaction.user.id if interaction.user else "?"

            if isinstance(original, discord.HTTPException) and original.status == 429:
                logger.warning(
                    "Rate limited on /%s for user %s (HTTP 429)",
                    cmd_name,
                    user_id,
                )
                from apps.discord_bot.core.view_helpers import safe_defer
                from apps.discord_bot.embeds.common_embeds import error_embed

                try:
                    if not interaction.response.is_done():
                        await safe_defer(interaction, ephemeral=True)
                    await interaction.followup.send(
                        embed=error_embed(
                            "Discord is temporarily rate-limiting requests. "
                            "Please try again in a minute."
                        ),
                        ephemeral=True,
                    )
                except discord.HTTPException:
                    pass
                return

            logger.error(
                "Unhandled app command error on /%s for user %s: %s",
                cmd_name,
                user_id,
                original,
                exc_info=original if isinstance(original, BaseException) else error,
            )
            from apps.discord_bot.embeds.common_embeds import error_embed

            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=error_embed("Something went wrong. Please try again."),
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        embed=error_embed("Something went wrong. Please try again."),
                        ephemeral=True,
                    )
            except discord.HTTPException:
                pass

        # Match recovery runs in on_ready once Discord is connected.

        # Register and start scheduler jobs
        # 1. Weekly league reset (Monday 00:00 UTC) — bot Division Rank ladder only
        self.scheduler.add_job(weekly_league_reset_job, "cron", day_of_week="mon", hour=0, minute=0, args=[self])
        # 2. Auto simulation of expired fixtures (every 10 minutes)
        self.scheduler.add_job(auto_sim_expired_fixtures_job, "interval", minutes=10, args=[self])
        # 3. League matchday closing reminders (hourly, deduped per matchday)
        self.scheduler.add_job(league_matchday_reminder_job, "interval", hours=1, args=[self])
        self.scheduler.start()
        logger.info("APScheduler initialized and jobs started.")

        # Start a simple web server for Render health checks and UptimeRobot pings if PORT exists
        port = os.environ.get("PORT")
        if port:
            try:
                port_int = int(port)
                import asyncio
                asyncio.create_task(self._start_web_server(port_int))
            except ValueError:
                logger.error(f"Invalid PORT environment variable value: {port}. Web server not started.")

    async def _start_web_server(self, port: int) -> None:
        from aiohttp import web
        
        async def handle_health(request):
            return web.json_response({
                "status": "ok",
                "bot": self.user.name if self.user else "connecting"
            })

        app = web.Application()
        app.router.add_get("/", handle_health)
        app.router.add_get("/health", handle_health)
        
        self._web_runner = web.AppRunner(app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(self._web_runner, "0.0.0.0", port)
        await self._web_site.start()
        logger.info(f"Web server started on port {port} for Render health checks.")

    async def close(self) -> None:
        """
        Cleanly closes the bot, stops background jobs, web server, and releases DB connections.
        """
        logger.info("Stopping background web server...")
        if hasattr(self, "_web_site") and self._web_site:
            try:
                await self._web_site.stop()
            except Exception as e:
                logger.warning(f"Error stopping web site: {e}")
        if hasattr(self, "_web_runner") and self._web_runner:
            try:
                await self._web_runner.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up web runner: {e}")

        logger.info("Stopping background scheduler...")
        if hasattr(self, "scheduler") and self.scheduler.running:
            try:
                self.scheduler.shutdown()
            except Exception as e:
                logger.error(f"Failed to stop background scheduler: {e}", exc_info=True)

        logger.info("Releasing database client connection pools...")
        try:
            from apps.discord_bot.db.client import close_client
            await close_client()
        except Exception as e:
            logger.error(f"Failed to close Supabase client sessions: {e}", exc_info=True)

        await super().close()
        logger.info("Shutdown sequence completed.")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        
        # Check if we should sync to a specific guild for local development
        guild_id = os.environ.get("GUILD_ID")
        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Command tree synchronized locally to Guild ID {guild_id} with {len(synced)} commands.")
            else:
                logger.info("Synchronizing application command tree globally...")
                synced = await self.tree.sync()
                logger.info(f"Command tree synchronized globally with {len(synced)} commands.")
        except Exception as e:
            logger.error(f"Failed to sync command tree: {e}", exc_info=True)

        try:
            from apps.discord_bot.core.match_recovery import recover_interrupted_matches
            await recover_interrupted_matches(self)
        except Exception as e:
            logger.error(f"Match recovery failed on startup: {e}", exc_info=True)

        try:
            from apps.discord_bot.tasks.level_reward_notifier import notify_pending_level_rewards
            await notify_pending_level_rewards(self)
        except Exception as e:
            logger.error(f"Level reward notification failed on startup: {e}", exc_info=True)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        try:
            from apps.discord_bot.db.client import get_client
            from apps.discord_bot.core.guild_resolver import pause_seasons_for_guild

            db = await get_client()
            paused = await pause_seasons_for_guild(db, guild.id, "bot_removed")
            if paused:
                logger.info(
                    "Paused %d league season(s) after leaving guild %s (%s)",
                    paused,
                    guild.id,
                    guild.name,
                )
        except Exception:
            logger.exception("Failed to pause seasons after leaving guild %s", guild.id)

def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN is missing from environment variables.")
        return
        
    bot = ElevenBossBot()
    bot.run(token)

if __name__ == "__main__":
    main()

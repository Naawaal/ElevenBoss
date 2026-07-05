# apps/discord_bot/main.py
from __future__ import annotations
import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.discord_bot.core.thread_manager import ThreadManager
from apps.discord_bot.core.scheduler_jobs import energy_regen_job, weekly_league_reset_job, auto_sim_expired_fixtures_job

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
            "apps.discord_bot.cogs.gacha_cog",
            "apps.discord_bot.cogs.squad_cog",
            "apps.discord_bot.cogs.player_cog",
            "apps.discord_bot.cogs.profile_cog",
            "apps.discord_bot.cogs.economy_cog",
            "apps.discord_bot.cogs.development_cog",
            "apps.discord_bot.cogs.marketplace_cog",
            "apps.discord_bot.cogs.battle_cog",
            "apps.discord_bot.cogs.admin_cog",
            "apps.discord_bot.cogs.league_cog"
        ]

    async def setup_hook(self) -> None:
        # Load cogs
        for cog in self.cogs_list:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}", exc_info=True)

        # Register and start scheduler jobs
        # 1. Passive energy regen (every 5 minutes)
        self.scheduler.add_job(energy_regen_job, "interval", minutes=5)
        # 2. Weekly league reset (Monday 00:00 UTC)
        self.scheduler.add_job(weekly_league_reset_job, "cron", day_of_week="mon", hour=0, minute=0, args=[self])
        # 3. Auto simulation of expired fixtures (every 10 minutes)
        self.scheduler.add_job(auto_sim_expired_fixtures_job, "interval", minutes=10)
        self.scheduler.start()
        logger.info("APScheduler initialized and jobs started.")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        logger.info("Synchronizing application command tree...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Command tree synchronized with {len(synced)} commands.")
        except Exception as e:
            logger.error(f"Failed to sync command tree: {e}", exc_info=True)

def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN is missing from environment variables.")
        return
        
    bot = ElevenBossBot()
    bot.run(token)

if __name__ == "__main__":
    main()

"""
ElevenBoss Discord Bot — Entry Point
=====================================
Execution order:
  1. Load config and validate it
  2. Set up rotating structured logging
  3. Initialize Sentry (error tracking)
  4. Instantiate and run ElevenBossBot

Run:
    python main.py
"""

import argparse
import asyncio
import logging
import sys
from app.logging_config import setup_logging
from app.config import config, validate_config, ConfigurationError
from app.error_reporting import init_error_reporting, capture_exception
from app.bot import ElevenBossBot

# Set up logging first so configuration or startup errors can be logged properly
setup_logging()
logger = logging.getLogger("app.main")

async def run_bot(sync_mode: str):
    # Validate configuration
    try:
        validate_config()
    except ConfigurationError as ce:
        logger.critical(f"Configuration Error: {ce}")
        sys.exit(1)

    # Initialize Sentry / crash reporting
    init_error_reporting()


    # Instantiate the bot
    bot = ElevenBossBot()

    # If syncing mode is requested, login, sync slash commands, and exit immediately
    if sync_mode:
        try:
            async with bot:
                logger.info(f"Logging in to sync commands (mode={sync_mode})...")
                await bot.login(config.DISCORD_TOKEN)
                await bot.setup_hook()
                
                if sync_mode == "guild":
                    if not config.GUILD_ID:
                        logger.critical("GUILD_ID missing from .env. Guild-scoped sync aborted.")
                        sys.exit(1)
                    import discord
                    guild = discord.Object(id=int(config.GUILD_ID))
                    bot.tree.copy_global_to(guild=guild)
                    bot.tree.remove_command("admin", guild=guild)
                    bot.tree.remove_command("settings", guild=guild)
                    synced = await bot.tree.sync(guild=guild)
                    logger.info(f"Successfully synced {len(synced)} commands to guild: {config.GUILD_ID}")
                else:
                    logger.info("Syncing slash commands globally... (may take up to an hour to propagate)")
                    synced = await bot.tree.sync()
                    logger.info(f"Successfully synced {len(synced)} commands globally.")
                await bot.close()
        except Exception as e:
            logger.critical(f"Failed to sync commands: {e}", exc_info=e)
            capture_exception(e)
            sys.exit(1)
        return

    # Normal execution path
    try:
        logger.info("Starting ElevenBoss Discord bot...")
        async with bot:
            await bot.start(config.DISCORD_TOKEN, reconnect=True)
    except Exception as e:
        logger.critical("Bot crashed during runtime execution.", exc_info=e)
        capture_exception(e)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ElevenBoss Discord Bot")
    parser.add_argument(
        "--sync", 
        choices=["global", "guild"], 
        help="Sync application commands to Discord (global or guild-scoped) and exit immediately."
    )
    args = parser.parse_args()


    try:
        asyncio.run(run_bot(sync_mode=args.sync))
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
    except Exception as e:
        logger.critical("Fatal initialization failure.", exc_info=e)
        sys.exit(1)

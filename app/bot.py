import logging
import os
import discord
from discord.ext import commands
from app.config import config
from app.error_reporting import capture_exception

logger = logging.getLogger("app.bot")

class ElevenBossBot(commands.Bot):
    def __init__(self):
        # Using least-privilege default intents (no privileged intents)
        intents = discord.Intents.default()
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Register tree error handler for slash commands
        self.tree.on_error = self.on_app_command_error

        # Dynamically load all cogs under app/cogs
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        logger.info("Initializing cog loading lifecycle...")
        
        loaded_cogs = []
        failed_cogs = []

        if os.path.exists(cogs_dir):
            for filename in os.listdir(cogs_dir):
                if filename.endswith(".py") and filename != "__init__.py":
                    cog_name = f"app.cogs.{filename[:-3]}"
                    try:
                        await self.load_extension(cog_name)
                        loaded_cogs.append(cog_name)
                        logger.info(f"Loaded cog: {cog_name}")
                    except Exception as e:
                        failed_cogs.append((cog_name, e))
                        logger.error(f"Failed to load cog {cog_name}: {e}", exc_info=e)
                        capture_exception(e)
        else:
            logger.warning(f"Cogs directory not found at: {cogs_dir}")

        if loaded_cogs:
            logger.info(f"Successfully loaded cogs: {', '.join(loaded_cogs)}")
        if failed_cogs:
            logger.error(f"Failed loading cogs summary: {len(failed_cogs)} cog(s) failed loading.")

        # Development Auto-Sync to Guild
        # Automatically syncs slash commands to the test guild on bot restart if in dev env
        if config.ENVIRONMENT == "development" and config.GUILD_ID:
            try:
                guild = discord.Object(id=int(config.GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Development Auto-Sync: Successfully synced {len(synced)} slash commands to guild: {config.GUILD_ID}")
            except Exception as e:
                logger.error(f"Development Auto-Sync: Failed to sync commands to guild {config.GUILD_ID}: {e}", exc_info=e)
                capture_exception(e)

    async def on_ready(self):
        logger.info(f"ElevenBoss logged in successfully as {self.user} (ID: {self.user.id if self.user else 'Unknown'})")
        logger.info(f"Guild count: {len(self.guilds)} server(s) connected.")

    async def close(self):
        logger.info("Initiating graceful shutdown for ElevenBoss...")
        await super().close()
        logger.info("Shutdown sequence completed.")

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        """Handle errors that occur within application (Slash) commands."""
        # Unwrap CommandInvokeError to get the actual raised exception
        actual_error = error
        if isinstance(error, discord.app_commands.CommandInvokeError):
            actual_error = error.original

        # Log command failure locally
        logger.error(
            f"AppCommandError in command '{interaction.command.name if interaction.command else 'Unknown'}' "
            f"by user {interaction.user.name} ({interaction.user.id}): {actual_error}",
            exc_info=actual_error
        )

        # Classify errors to filter out benign user input/permission errors from Sentry alerts
        user_facing_errors = (
            discord.app_commands.CommandOnCooldown,
            discord.app_commands.MissingPermissions,
            discord.app_commands.BotMissingPermissions,
            discord.app_commands.CheckFailure
        )

        if isinstance(actual_error, user_facing_errors):
            if isinstance(actual_error, discord.app_commands.CommandOnCooldown):
                error_message = f"This command is on cooldown. Try again in {actual_error.retry_after:.2f}s."
            elif isinstance(actual_error, discord.app_commands.MissingPermissions):
                perms = ", ".join(actual_error.missing_permissions)
                error_message = f"You do not have the required permissions to run this command: `{perms}`"
            elif isinstance(actual_error, discord.app_commands.BotMissingPermissions):
                perms = ", ".join(actual_error.missing_permissions)
                error_message = f"The bot lacks permissions to run this command: `{perms}`"
            else:
                error_message = f"Command execution denied: {actual_error}"
        else:
            # System errors: Send to error reporting system
            capture_exception(actual_error)
            error_message = "An unexpected runtime error occurred. Our developers have been notified."

        # Send response to user
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to respond to user for AppCommandError: {e}", exc_info=e)


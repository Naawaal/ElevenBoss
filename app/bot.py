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
        # Bind bot reference to permission service
        from app.services import permission_service
        permission_service.bot = self

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

        # Global Sync (required for DM-only slash commands to work in DMs)
        try:
            synced_global = await self.tree.sync()
            logger.info(f"Global Sync: Successfully synced {len(synced_global)} slash commands globally (active in DMs).")
        except Exception as e:
            logger.error(f"Global Sync: Failed to sync commands globally: {e}", exc_info=e)
            capture_exception(e)

        # Run database migrations asynchronously in the background so it doesn't block bot startup/connection
        import asyncio
        asyncio.create_task(self._run_migrations_async())

        # Start scheduler
        from app.scheduler.scheduler import start_scheduler
        try:
            start_scheduler(self)
        except Exception as e:
            logger.error(f"Failed to start background scheduler: {e}", exc_info=e)
            capture_exception(e)

    async def _run_migrations_async(self):
        import asyncio
        try:
            from app.db.migrations import run_migrations
            logger.info("Scheduling background database migrations check...")
            await asyncio.to_thread(run_migrations)
        except Exception as e:
            logger.error(f"Background database migrations check failed: {e}", exc_info=e)
            capture_exception(e)

    async def on_ready(self):
        logger.info(f"ElevenBoss logged in successfully as {self.user} (ID: {self.user.id if self.user else 'Unknown'})")
        logger.info(f"Guild count: {len(self.guilds)} server(s) connected.")

    async def close(self):
        logger.info("Initiating graceful shutdown for ElevenBoss...")
        from app.scheduler.scheduler import shutdown_scheduler
        try:
            shutdown_scheduler()
        except Exception as e:
            logger.error(f"Failed to stop background scheduler: {e}", exc_info=e)
            capture_exception(e)
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

        # Log command failure locally (suppress traceback for transient/expired Discord interactions)
        if isinstance(actual_error, discord.NotFound) and actual_error.code == 10062:
            logger.warning(
                f"AppCommandError in command '{interaction.command.name if interaction.command else 'Unknown'}' "
                f"by user {interaction.user.name} ({interaction.user.id}): Interaction expired (Unknown interaction)"
            )
        elif isinstance(actual_error, discord.HTTPException) and actual_error.code in (40060, 50027):
            logger.warning(
                f"AppCommandError in command '{interaction.command.name if interaction.command else 'Unknown'}' "
                f"by user {interaction.user.name} ({interaction.user.id}): Interaction already acknowledged or invalid token"
            )
        else:
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
        elif isinstance(actual_error, discord.NotFound) and actual_error.code == 10062:
            # Benign Discord API error: Unknown interaction (expired token)
            error_message = "This interaction has expired. Please run the command again."
        elif isinstance(actual_error, discord.HTTPException) and actual_error.code in (40060, 50027):
            # Benign Discord API error: Interaction already acknowledged or invalid webhook token
            error_message = "This interaction has already been acknowledged or expired."
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
        except (discord.NotFound, discord.HTTPException) as de:
            logger.warning(f"Could not send error response for AppCommandError (interaction likely expired/invalid): {de}")
        except Exception as e:
            logger.error(f"Failed to respond to user for AppCommandError: {e}", exc_info=e)


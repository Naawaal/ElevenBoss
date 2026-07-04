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
        # Bind bot reference to services
        from app.services import permission_service
        permission_service.bot = self
        from app.services.announcement_service import AnnouncementService
        AnnouncementService.bot = self


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

        # Development Auto-Sync to Guild (using copy-sync to update commands instantly in development)
        if config.ENVIRONMENT == "development" and config.GUILD_ID:
            try:
                guild = discord.Object(id=int(config.GUILD_ID))
                # 1. Copy global commands into guild scope for instant slash-command updates
                self.tree.copy_global_to(guild=guild)
                # Remove the DM-only commands from the guild tree so they are not synced to the guild
                self.tree.remove_command("admin", guild=guild)
                self.tree.remove_command("settings", guild=guild)
                synced = await self.tree.sync(guild=guild)
                
                # 2. To avoid duplicates of the guild commands, we want to clear them from the global scope.
                # But we must keep "admin" and "settings" in the global scope so they work in DMs.
                # So we remove all commands from the global tree *except* "admin" and "settings".
                global_cmds = self.tree.get_commands(guild=None)
                for cmd in global_cmds:
                    if cmd.name not in ("admin", "settings"):
                        self.tree.remove_command(cmd.name, guild=None)
                await self.tree.sync()
                logger.info(f"Development Auto-Sync: Successfully synced {len(synced)} slash commands to guild: {config.GUILD_ID}")
            except Exception as e:
                logger.error(f"Development Auto-Sync: Failed to sync commands to guild {config.GUILD_ID}: {e}", exc_info=e)
                capture_exception(e)
        else:
            logger.info("Normal startup: Skipping automatic global command sync to prevent latency. Use CLI --sync global to sync commands.")

        # Run database migrations asynchronously in the background so it doesn't block bot startup/connection
        import asyncio
        asyncio.create_task(self._run_migrations_async())

        # Sweep any matchday locks left stuck in RUNNING state by a previous hard crash.
        # Runs concurrently with migrations — the sweep is DML only, no DDL conflict.
        # The scheduler starts after both tasks are *created* (not after they complete),
        # so the first game-loop tick (~1 min) could fire before the sweep finishes;
        # the inline staleness check in matchday_service.py covers that narrow window.
        asyncio.create_task(self._sweep_stale_locks_on_startup())

        # Start scheduler
        from app.scheduler.scheduler import start_scheduler
        try:
            start_scheduler(self)
        except Exception as e:
            logger.error(f"Failed to start background scheduler: {e}", exc_info=e)
            capture_exception(e)

        # Start a simple web server for Render health checks and UptimeRobot pings if PORT env var exists
        port = os.getenv("PORT")
        if port:
            self.loop.create_task(self.start_web_server(int(port)))

    async def start_web_server(self, port: int):
        """
        Starts a lightweight web server on the bot's existing event loop.
        Allows Render to perform successful HTTP health checks and UptimeRobot to ping the service.
        """
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

    async def close(self):
        """
        Cleanly closes the bot and shuts down the background web server if running.
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
        await super().close()

    async def _run_migrations_async(self):
        import asyncio
        try:
            from app.db.migrations import run_migrations
            logger.info("Scheduling background database migrations check...")
            await asyncio.to_thread(run_migrations)
        except Exception as e:
            logger.error(f"Background database migrations check failed: {e}", exc_info=e)
            capture_exception(e)

    async def _sweep_stale_locks_on_startup(self):
        """
        On every bot (re)start, atomically mark any matchday job locks stuck in RUNNING
        state (older than STALE_MATCHDAY_LOCK_HOURS hours) as FAILED, so the next
        scheduler tick can acquire a fresh lock and proceed normally.

        This covers the common crash-then-restart scenario. The inline staleness check
        in matchday_service.py covers the rarer crash-without-restart case.
        """
        from datetime import timedelta, timezone, datetime
        from app.db.session import get_session
        from app.repositories import mark_stale_running_jobs_failed, STALE_MATCHDAY_LOCK_HOURS

        cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_MATCHDAY_LOCK_HOURS)
        try:
            async with get_session() as session:
                count = await mark_stale_running_jobs_failed(
                    session,
                    job_key_prefix="matchday:",
                    started_before=cutoff,
                )
                await session.commit()
            if count:
                logger.warning(
                    f"startup_stale_lock_sweep: recovered {count} stuck matchday lock(s) "
                    f"(threshold={STALE_MATCHDAY_LOCK_HOURS}h)"
                )
            else:
                logger.debug("startup_stale_lock_sweep: no stale matchday locks found")
        except Exception as e:
            logger.error(f"startup_stale_lock_sweep failed: {e}", exc_info=e)
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


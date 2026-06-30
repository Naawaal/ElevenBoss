import logging
import os
import discord
from discord.ext import commands
import sentry_sdk

logger = logging.getLogger("discord")

class ElevenBossBot(commands.Bot):
    def __init__(self):
        # Using least-privilege intents as recommended for verification/approval
        intents = discord.Intents.default()
        super().__init__(
            command_prefix=commands.when_mentioned, # Primary fallback command prefix
            intents=intents,
            help_command=None # Custom help command implemented later
        )

    async def setup_hook(self):
        # Load cogs dynamically
        await self.load_extension("bot.cogs.general")
        logger.info("Cogs loaded successfully.")

        # Attach custom error handler to the CommandTree for Slash Commands
        self.tree.on_error = self.on_app_command_error

        # Command syncing strategy
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Successfully synced {len(synced)} commands to guild: {guild_id}")
            except Exception as e:
                logger.error(f"Failed to sync commands to guild {guild_id}: {e}", exc_info=e)
        else:
            try:
                logger.info("Syncing slash commands globally... (may take up to an hour to propagate)")
                synced = await self.tree.sync()
                logger.info(f"Successfully synced {len(synced)} commands globally.")
            except Exception as e:
                logger.error(f"Failed to sync commands globally: {e}", exc_info=e)

    async def on_ready(self):
        logger.info(f"ElevenBoss logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds.")

    async def on_app_command_error(
        self, 
        interaction: discord.Interaction, 
        error: discord.app_commands.AppCommandError
    ):
        # Log to local rotating files
        logger.error(
            f"AppCommandError in command '{interaction.command.name if interaction.command else 'Unknown'}' "
            f"by user {interaction.user.name} ({interaction.user.id}): {error}", 
            exc_info=error
        )
        
        # Capture in Sentry
        sentry_sdk.capture_exception(error)

        # Build user-friendly error response
        error_message = "An unexpected error occurred. The developers have been notified."

        # Handle typical slash command errors
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            error_message = f"This command is on cooldown. Try again in {error.retry_after:.2f}s."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            error_message = f"You are missing the required permissions to run this command: `{perms}`"
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            error_message = f"The bot is missing permissions to run this command: `{perms}`"

        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send error message response to user: {e}", exc_info=e)

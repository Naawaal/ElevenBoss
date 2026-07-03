# app/cogs/training_cog.py

import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers.training_handler import handle_open_training_dashboard
from app.ui.handlers.session import ui_session_manager
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.training_cog")


class TrainingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="training", description="Manage your club's training plans, intensity, and player progress.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def training_command(self, interaction: discord.Interaction):
        """
        Open the training dashboard for the requesting manager's club.
        """
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        session = ui_session_manager.create_session(interaction.user.id, interaction.guild_id)
        nonce = session.session_id

        try:
            view = await handle_open_training_dashboard(interaction.guild_id, interaction.user.id, nonce)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"training_command_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"ui_error: failed to open training: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading training. Please try again."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(TrainingCog(bot))

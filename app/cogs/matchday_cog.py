# app/cogs/matchday_cog.py

import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers import (
    handle_view_matchday_status,
    handle_run_matchday,
)
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.matchday_cog")

@app_commands.guild_only()
class MatchdayGroup(commands.GroupCog, name="matchday"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="status",
        description="View the simulation status of the current matchweek."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def status_command(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_view_matchday_status(interaction.guild_id, interaction.user)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"matchday_status_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"matchday_error: status command failed for guild_id={interaction.guild_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading matchday status."
            )

    @app_commands.command(
        name="run",
        description="[Admin] Simulate all scheduled fixtures for the current matchweek."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def run_command(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # We pass is_admin check results to the handler/service
            from app.ui.handlers.league_handler import check_admin_permission
            is_admin = await check_admin_permission(interaction.guild_id, interaction.user)
            if not is_admin:
                await interaction.edit_original_response(
                    content="❌ Only server administrators or game admins can simulate the matchday."
                )
                return

            from app.ui.handlers.session import ui_session_manager
            session = ui_session_manager.create_session(interaction.user.id, interaction.guild_id)
            nonce = session.session_id

            view = await handle_run_matchday(interaction.guild_id, interaction.user, nonce)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"matchday_run_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"matchday_error: run command failed for guild_id={interaction.guild_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while simulating matches."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(MatchdayGroup(bot))

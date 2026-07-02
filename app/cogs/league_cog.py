import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.services.league_service import create_league, join_league, start_league
from app.ui.handlers.league_handler import handle_open_league_dashboard, check_admin_permission
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.league_cog")

@app_commands.guild_only()
class LeagueGroup(commands.GroupCog, name="league"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="join", description="Join the draft league with your registered club.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def join_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        res = await join_league(interaction.guild_id, interaction.user.id)
        if not res.success:
            await interaction.edit_original_response(content=f"❌ {res.message}")
            return

        # Refreshes the dashboard
        try:
            view, file = await handle_open_league_dashboard(
                interaction.guild_id, 
                interaction.user,
                banner=f"✅ {res.message}"
            )
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
        except Exception as e:
            logger.error(f"Failed to load league dashboard after join: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content=f"✅ {res.message}")


    @app_commands.command(name="status", description="View the current league status dashboard.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def status_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            view, file = await handle_open_league_dashboard(interaction.guild_id, interaction.user)
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
        except ValueError as ve:
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"Failed to fetch league status: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="❌ An unexpected error occurred while fetching the league status.")

async def setup(bot: commands.Bot):
    await bot.add_cog(LeagueGroup(bot))

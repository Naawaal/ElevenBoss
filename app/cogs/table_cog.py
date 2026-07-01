import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers.league_handler import handle_view_table
from app.ui.handlers.session import ui_session_manager
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.table_cog")

class TableCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="table", description="View the current league standings table.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def table_command(self, interaction: discord.Interaction):
        # Must be in a guild
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Create a fresh UI session for the table view
            session = ui_session_manager.create_session(interaction.user.id, interaction.guild_id)
            view, file = await handle_view_table(interaction.guild_id, interaction.user, session.session_id)
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
        except ValueError as ve:
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"Failed to fetch table: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="❌ An unexpected error occurred while loading the standings table.")

async def setup(bot: commands.Bot):
    await bot.add_cog(TableCog(bot))

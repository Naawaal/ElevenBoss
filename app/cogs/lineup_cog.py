# app/cogs/lineup_cog.py

import logging
import discord
from discord import app_commands
from discord.ext import commands
from app.ui.handlers.lineup_handler import handle_open_lineup_screen
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.lineup_cog")

class LineupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lineup", description="View and manage your active formation and starting XI.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def lineup_command(self, interaction: discord.Interaction):
        # Must be in a guild context
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view, file = await handle_open_lineup_screen(
                interaction.guild_id,
                interaction.user.id,
                manager_name=interaction.user.display_name
            )
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
        except ValueError as ve:
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"ui_error: failed to open lineup screen: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="❌ An unexpected error occurred while loading your lineup.")

async def setup(bot: commands.Bot):
    await bot.add_cog(LineupCog(bot))

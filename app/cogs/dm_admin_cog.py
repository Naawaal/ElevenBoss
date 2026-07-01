# app/cogs/dm_admin_cog.py

import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers.dm_admin_handler import handle_open_admin_console

logger = logging.getLogger("app.cogs.dm_admin_cog")

class DMAdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin", description="Open the private ElevenBoss Admin Override Dashboard (DMs only).")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def admin(self, interaction: discord.Interaction):
        # Must be in DM
        if interaction.guild_id is not None:
            await interaction.response.send_message("❌ This command has moved to DM. Please DM me and run `/admin`.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            view = await handle_open_admin_console(interaction.user)
            await interaction.followup.send(view=view)
        except Exception as e:
            logger.error(f"dm_admin_error: failed to open console: {e}", exc_info=e)
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DMAdminCog(bot))

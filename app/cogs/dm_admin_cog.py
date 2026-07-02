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

    # Create the top-level 'admin' group
    admin = app_commands.Group(
        name="admin",
        description="ElevenBoss Admin Overrides Console",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(guild=False, dm_channel=True, private_channel=True)
    )

    # Subcommand to open the interactive admin console dashboard
    @admin.command(name="console", description="Open the private ElevenBoss Admin Override Dashboard.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def console(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            view = await handle_open_admin_console(interaction.user)
            await interaction.followup.send(view=view)
        except Exception as e:
            logger.error(f"dm_admin_error: failed to open console: {e}", exc_info=e)
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DMAdminCog(bot))

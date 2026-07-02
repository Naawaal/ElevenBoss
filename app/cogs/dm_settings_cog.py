# app/cogs/dm_settings_cog.py

import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers.dm_settings_handler import handle_open_settings_console

logger = logging.getLogger("app.cogs.dm_settings_cog")

class DMSettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Open the private ElevenBoss Settings Console (DMs only).")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def settings(self, interaction: discord.Interaction):
        # Must be in DM
        if interaction.guild_id is not None:
            await interaction.response.send_message("❌ This command has moved to DM. Please DM me and run `/settings`.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            view = await handle_open_settings_console(interaction.user)
            await interaction.followup.send(view=view)
        except Exception as e:
            logger.error(f"dm_settings_error: failed to open console: {e}", exc_info=e)
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DMSettingsCog(bot))

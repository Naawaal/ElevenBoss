# app/cogs/match_cog.py

import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers import (
    handle_view_recent_match,
    handle_view_match_detail,
)
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.match_cog")

@app_commands.guild_only()
class MatchGroup(commands.GroupCog, name="match"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="recent",
        description="View details of the most recently simulated match."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def recent_command(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_view_recent_match(interaction.guild_id, interaction.user)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"match_recent_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"match_error: recent command failed for guild_id={interaction.guild_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading match report."
            )

    @app_commands.command(
        name="view",
        description="View details of a specific match by fixture ID."
    )
    @app_commands.describe(fixture_id="The unique ID of the fixture/match.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def view_command(self, interaction: discord.Interaction, fixture_id: str):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_view_match_detail(interaction.guild_id, interaction.user, fixture_id)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"match_view_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, fixture_id={fixture_id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"match_error: view command failed for fixture_id={fixture_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading match report."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(MatchGroup(bot))

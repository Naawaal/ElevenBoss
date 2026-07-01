"""
Fixtures Cog — Discord slash commands for viewing the fixture schedule.

Commands:
  /fixtures view  — View the current season week's fixtures.
  /fixtures week  — View fixtures for a specific week.

Fixture generation is handled automatically during /league start.
All business logic is in fixture_service.py.
All UI rendering is in fixture_renderer.py and fixture layouts.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers.fixtures_handler import (
    handle_view_current_week_fixtures,
    handle_view_week_fixtures,
)
from app.ui.handlers.session import ui_session_manager
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.fixtures_cog")


@app_commands.guild_only()
class FixturesGroup(commands.GroupCog, name="fixtures"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    # ── /fixtures view ─────────────────────────────────────────────

    @app_commands.command(
        name="view",
        description="View the fixture schedule for the active season's current week."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def view_command(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        session = ui_session_manager.create_session(interaction.user.id, interaction.guild_id)
        nonce = session.session_id

        try:
            view = await handle_view_current_week_fixtures(interaction.guild_id, interaction.user, nonce)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"fixtures_view_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"fixtures_error: view command failed for guild_id={interaction.guild_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading fixtures."
            )

    # ── /fixtures week ─────────────────────────────────────────────

    @app_commands.command(
        name="week",
        description="View fixtures for a specific week in the current season."
    )
    @app_commands.describe(week="The week number to view (e.g. 3).")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def week_command(self, interaction: discord.Interaction, week: int):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        if week < 1:
            await interaction.response.send_message(
                "❌ Week number must be 1 or greater.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        session = ui_session_manager.create_session(interaction.user.id, interaction.guild_id)
        nonce = session.session_id

        try:
            view = await handle_view_week_fixtures(interaction.guild_id, interaction.user, nonce, week)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            logger.info(
                f"fixtures_week_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, week={week}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"fixtures_error: week command failed for guild_id={interaction.guild_id}, "
                f"week={week}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading fixtures."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(FixturesGroup(bot))

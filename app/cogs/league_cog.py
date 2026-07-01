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

    @app_commands.command(name="create", description="Create a new draft league for this server.")
    @app_commands.describe(
        league_name="The name of the league (3-40 characters).",
        league_size="The number of clubs allowed in the league."
    )
    @app_commands.choices(league_size=[
        app_commands.Choice(name="8 Clubs", value=8),
        app_commands.Choice(name="10 Clubs", value=10),
        app_commands.Choice(name="12 Clubs", value=12),
        app_commands.Choice(name="16 Clubs", value=16)
    ])
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def create_command(self, interaction: discord.Interaction, league_name: str, league_size: app_commands.Choice[int]):
        # Check permissions
        is_admin = await check_admin_permission(interaction.guild_id, interaction.user)
        if not is_admin:
            logger.warning(f"league_interaction_rejected: reason=permission_denied, user_id={interaction.user.id}, action=create")
            await interaction.response.send_message("❌ Only server administrators or game admins can create a league.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        res = await create_league(interaction.guild_id, league_name, league_size.value)
        if not res.success:
            logger.warning(f"league_create_failed: guild_id={interaction.guild_id}, reason={res.message}")
            await interaction.edit_original_response(content=f"❌ {res.message}")
            return

        # Open the dashboard for the newly created league
        try:
            view, file = await handle_open_league_dashboard(
                interaction.guild_id, 
                interaction.user,
                banner="✅ **League created successfully!**"
            )
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
        except Exception as e:
            logger.error(f"Failed to load league dashboard after create: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="✅ League created successfully! Run `/league status` to view it.")

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

    @app_commands.command(name="start", description="Bootstrap the league season. Fills empty slots with bots.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def start_command(self, interaction: discord.Interaction):
        # Check permissions
        is_admin = await check_admin_permission(interaction.guild_id, interaction.user)
        if not is_admin:
            logger.warning(f"league_interaction_rejected: reason=permission_denied, user_id={interaction.user.id}, action=start")
            await interaction.response.send_message("❌ Only server administrators or game admins can start the league season.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        res = await start_league(interaction.guild_id)
        if not res.success:
            await interaction.edit_original_response(content=f"❌ {res.message}")
            return

        # Return active season summary dashboard
        try:
            banner_content = (
                f"✅ **League season started successfully!**\n"
                f"• League Size: `{res.league_size}`\n"
                f"• Human Clubs: `{res.human_clubs}`\n"
                f"• Bot Clubs Generated: `{res.bot_clubs}`\n"
                f"• Season: `Season 1`"
            )
            view, file = await handle_open_league_dashboard(
                interaction.guild_id, 
                interaction.user,
                banner=banner_content
            )
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
        except Exception as e:
            logger.error(f"Failed to load league dashboard after start: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="✅ League started successfully! Run `/league status` to view.")

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

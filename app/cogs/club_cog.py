import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.custom_ids import decode_custom_id
from app.ui.handlers import (
    ui_session_manager,
    handle_open_locker_room,
    handle_view_club_dashboard,
    handle_view_help,
    handle_view_squad,
    handle_view_player_search,
    handle_view_player_detail,
    handle_search_player_by_name,
    handle_open_lineup_screen,
    handle_select_formation,
    handle_auto_lineup,
    handle_save_lineup,
    handle_refresh_lineup
)
from app.error_reporting import capture_exception
from app.ui.components import container, text_display, V2View

logger = logging.getLogger("app.cogs.club_cog")

class ClubCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="club", description="Open your football club's Locker Room dashboard.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def club_command(self, interaction: discord.Interaction):
        # Must be in a guild
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_open_locker_room(interaction.guild_id, interaction.user.id)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"ui_error: failed to open locker room: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="❌ An unexpected error occurred while loading your club. Please try again.")

    @app_commands.command(name="squad", description="Open your squad list (paginated).")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def squad_command(self, interaction: discord.Interaction):
        # Must be in a guild
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_view_squad(interaction.guild_id, interaction.user.id, page=1)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"ui_error: failed to open squad: {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="❌ An unexpected error occurred while loading your squad.")

    @app_commands.command(name="player", description="View detailed stats for a player in your squad.")
    @app_commands.describe(name="The name of the player you want to view.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def player_command(self, interaction: discord.Interaction, name: str):
        # Must be in a guild
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        # Pre-validate query length
        trimmed_query = name.strip()
        if len(trimmed_query) < 2:
            await interaction.response.send_message("❌ Player name search query must be at least 2 characters.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_search_player_by_name(interaction.guild_id, interaction.user.id, trimmed_query)
            await interaction.edit_original_response(view=view)
        except ValueError as ve:
            await interaction.edit_original_response(content=f"❌ {str(ve)}")
        except Exception as e:
            logger.error(f"ui_error: failed to search player '{name}': {e}", exc_info=e)
            capture_exception(e)
            await interaction.edit_original_response(content="❌ An unexpected error occurred while searching for the player.")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        Global interaction gateway to intercept components clicks for FCM.
        """
        # We only handle component interactions (Buttons / String Selects)
        if interaction.type != discord.InteractionType.component:
            return

        custom_id_str = interaction.data.get("custom_id")
        if not custom_id_str or not custom_id_str.startswith("fcm:"):
            return

        logger.info(f"ui_interaction_received: custom_id={custom_id_str}, user_id={interaction.user.id}, guild_id={interaction.guild_id}")

        try:
            custom_id = decode_custom_id(custom_id_str)
        except ValueError as e:
            logger.warning(f"ui_custom_id_invalid: custom_id={custom_id_str}, error={e}")
            await self.send_error_response(interaction, "Invalid or unsupported interactive element.")
            return

        # Ensure we are in a guild context
        if not interaction.guild_id:
            logger.warning(f"ui_interaction_rejected: reason=dm_not_allowed, user_id={interaction.user.id}")
            await self.send_error_response(interaction, "Interactive menus are not supported in DMs.")
            return

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        nonce = custom_id.nonce

        try:
            # Handle close button immediately
            if custom_id.scope == "nav" and custom_id.action == "close":
                session = ui_session_manager.get_session(nonce)
                if session:
                    # Validate ownership before deleting session
                    if session.discord_user_id != user_id:
                        logger.warning(f"ui_unauthorized_click: scope=nav, action=close, user_id={user_id}, owner_id={session.discord_user_id}")
                        await self.send_error_response(interaction, "You do not own this interactive menu. Please run the command to open your own.")
                        return
                    ui_session_manager._sessions.pop(nonce, None)
                
                comp_payload = [
                    container([
                        text_display("❌ *Menu closed.*")
                    ])
                ]
                await interaction.response.edit_message(view=V2View(comp_payload))
                logger.info(f"ui_interaction_received: closed session={nonce}, user_id={user_id}")
                return

            # Defer response immediately to prevent 3-second Discord timeouts
            await interaction.response.defer()

            new_view = None

            # Route to handlers based on scope and action
            if custom_id.scope == "locker":
                if custom_id.action == "open" and custom_id.target == "club":
                    new_view = await handle_view_club_dashboard(guild_id, user_id, nonce)
                elif custom_id.action == "view" and custom_id.target == "squad":
                    new_view = await handle_view_squad(guild_id, user_id, page=1, nonce=nonce)
                elif custom_id.action == "view" and custom_id.target == "help":
                    new_view = await handle_view_help(guild_id, user_id, nonce)
                elif custom_id.action == "refresh" and custom_id.target == "club":
                    new_view = await handle_open_locker_room(guild_id, user_id, nonce)

            elif custom_id.scope == "squad":
                if custom_id.action == "page":
                    page = int(custom_id.target)
                    new_view = await handle_view_squad(guild_id, user_id, page=page, nonce=nonce)
                elif custom_id.action == "refresh":
                    page = int(custom_id.target)
                    new_view = await handle_view_squad(guild_id, user_id, page=page, nonce=nonce)

            elif custom_id.scope == "player":
                if custom_id.action == "view":
                    if custom_id.target == "search":
                        new_view = await handle_view_player_search(guild_id, user_id, nonce)
                    elif custom_id.target == "select":
                        # Multi-select dropdown menu
                        if not interaction.data.get("values"):
                            raise ValueError("No player selected.")
                        selected_player_id = interaction.data["values"][0]
                        new_view = await handle_view_player_detail(guild_id, user_id, selected_player_id, nonce)
                    else:
                        new_view = await handle_view_player_detail(guild_id, user_id, custom_id.target, nonce)
                elif custom_id.action == "refresh":
                    new_view = await handle_view_player_detail(guild_id, user_id, custom_id.target, nonce)

            elif custom_id.scope == "lineup":
                if custom_id.action == "open" and custom_id.target == "main":
                    new_view = await handle_open_lineup_screen(guild_id, user_id, nonce)
                elif custom_id.action == "formation" and custom_id.target == "select":
                    if not interaction.data.get("values"):
                        raise ValueError("No formation selected.")
                    selected_formation = interaction.data["values"][0]
                    new_view = await handle_select_formation(guild_id, user_id, selected_formation, nonce)
                elif custom_id.action == "auto" and custom_id.target == "best":
                    new_view = await handle_auto_lineup(guild_id, user_id, nonce)
                elif custom_id.action == "save" and custom_id.target == "active":
                    new_view = await handle_save_lineup(guild_id, user_id, nonce)
                elif custom_id.action == "refresh" and custom_id.target == "main":
                    new_view = await handle_refresh_lineup(guild_id, user_id, nonce)

            elif custom_id.scope == "nav" and custom_id.action == "back":
                if custom_id.target == "locker":
                    new_view = await handle_open_locker_room(guild_id, user_id, nonce)
                elif custom_id.target == "squad":
                    session = ui_session_manager.get_session(nonce)
                    page = session.metadata.get("squad_page", 1) if session else 1
                    new_view = await handle_view_squad(guild_id, user_id, page=page, nonce=nonce)

            if isinstance(new_view, tuple):
                view, file = new_view
                await interaction.edit_original_response(view=view, attachments=[file] if file else [])
            elif new_view:
                await interaction.edit_original_response(view=new_view)
            else:
                logger.warning(f"ui_interaction_rejected: reason=unhandled_routing, scope={custom_id.scope}, action={custom_id.action}")
                await self.send_error_response(interaction, "Unhandled interaction action.")

        except ValueError as ve:
            # Handle user validation failures (e.g. session expired, not owner)
            logger.info(f"ui_interaction_rejected: reason=validation_error, message={ve}, user_id={user_id}")
            await self.send_error_response(interaction, str(ve))
        except Exception as e:
            # Handle unexpected crashes, report to Sentry
            logger.error(f"ui_error: unexpected error in on_interaction: {e}", exc_info=e)
            capture_exception(e)
            await self.send_error_response(interaction, "An unexpected error occurred. Please open a new menu.")

    async def send_error_response(self, interaction: discord.Interaction, message: str):
        """
        Sends an ephemeral validation error response safely.
        """
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)
        except Exception as e:
            logger.warning(f"Could not send error response to interaction: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ClubCog(bot))

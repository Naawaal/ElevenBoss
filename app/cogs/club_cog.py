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
    handle_refresh_lineup,
    handle_open_league_dashboard,
    handle_join_league,
    handle_start_league,
    handle_view_table,
    handle_refresh_table,
    handle_view_current_week_fixtures,
    handle_view_week_fixtures,
    handle_view_matchday_status,
    handle_run_matchday,
    handle_view_recent_match,
    handle_view_match_detail,
)
from app.error_reporting import capture_exception
from app.ui.components import container, text_display, V2View

logger = logging.getLogger("app.cogs.club_cog")

class ExtendDeadlineModal(discord.ui.Modal, title="Extend Registration Deadline"):
    new_deadline = discord.ui.TextInput(
        label="New Deadline",
        placeholder="e.g. Sunday 20:00 or 2026-07-05 20:00",
        required=True
    )
    timezone = discord.ui.TextInput(
        label="Timezone",
        placeholder="e.g. Asia/Kathmandu or UTC",
        default="Asia/Kathmandu",
        required=True
    )

    def __init__(self, guild_id: int, nonce: str, bot):
        super().__init__()
        self.guild_id = guild_id
        self.nonce = nonce
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from app.services.league_service import extend_deadline
        from app.ui.handlers.dm_admin_handler import handle_open_admin_dashboard
        
        res = await extend_deadline(self.guild_id, self.new_deadline.value, self.timezone.value)
        if res.success:
            new_view = await handle_open_admin_dashboard(self.guild_id, interaction.user, self.nonce)
            await interaction.followup.send(content=f"✅ {res.message}", ephemeral=True)
            await interaction.message.edit(view=new_view)
        else:
            await interaction.followup.send(content=f"❌ {res.message}", ephemeral=True)

class ScheduleSetupModal(discord.ui.Modal, title="Configure Matchday Schedule"):
    day = discord.ui.TextInput(
        label="Matchday Day of Week",
        placeholder="e.g. Sunday",
        required=True
    )
    time = discord.ui.TextInput(
        label="Matchday Time (HH:MM)",
        placeholder="e.g. 20:00",
        required=True
    )
    timezone = discord.ui.TextInput(
        label="Timezone",
        placeholder="e.g. Asia/Kathmandu or UTC",
        default="Asia/Kathmandu",
        required=True
    )
    channel_id = discord.ui.TextInput(
        label="Results Announcement Channel ID",
        placeholder="Optional numeric ID",
        required=False
    )

    def __init__(self, guild_id: int, nonce: str, bot):
        super().__init__()
        self.guild_id = guild_id
        self.nonce = nonce
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from app.services.settings_service import SettingsService
        from app.ui.handlers.dm_settings_handler import handle_open_settings_schedule
        
        # Get values
        d_val = self.day.value.strip()
        t_val = self.time.value.strip()
        tz_val = self.timezone.value.strip()
        ch_val = self.channel_id.value.strip() or None
        
        guild_obj = self.bot.get_guild(self.guild_id) if self.bot else None
        
        success, message = await SettingsService.update_schedule_settings(
            guild_id=self.guild_id,
            guild_obj=guild_obj,
            day=d_val,
            time=t_val,
            timezone=tz_val,
            channel_id=ch_val
        )
        
        if success:
            new_view = await handle_open_settings_schedule(self.guild_id, interaction.user, self.nonce)
            await interaction.followup.send(content=f"✅ {message}", ephemeral=True)
            await interaction.message.edit(view=new_view)
        else:
            await interaction.followup.send(content=f"❌ {message}", ephemeral=True)

class CreateLeagueModal(discord.ui.Modal, title="Create Draft League"):
    name = discord.ui.TextInput(
        label="League Name",
        placeholder="e.g. Champions League",
        required=True
    )
    size = discord.ui.TextInput(
        label="League Size (8, 10, 12, 16)",
        placeholder="e.g. 8",
        default="8",
        required=True
    )
    deadline = discord.ui.TextInput(
        label="Registration Deadline",
        placeholder="e.g. Sunday 20:00 (Optional)",
        required=False
    )
    timezone = discord.ui.TextInput(
        label="Timezone",
        placeholder="e.g. Asia/Kathmandu",
        default="Asia/Kathmandu",
        required=True
    )

    def __init__(self, guild_id: int, nonce: str, bot):
        super().__init__()
        self.guild_id = guild_id
        self.nonce = nonce
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from app.services.league_service import create_league
        from app.ui.handlers.dm_admin_handler import handle_open_admin_dashboard
        
        try:
            sz = int(self.size.value.strip())
            if sz not in (8, 10, 12, 16):
                raise ValueError("Size must be 8, 10, 12, or 16.")
        except ValueError:
            await interaction.followup.send(content="❌ League size must be 8, 10, 12, or 16.", ephemeral=True)
            return

        res = await create_league(
            guild_id=self.guild_id,
            league_name=self.name.value.strip(),
            league_size=sz,
            registration_deadline=self.deadline.value.strip() or None,
            registration_deadline_timezone=self.timezone.value.strip()
        )
        
        if res.success:
            new_view = await handle_open_admin_dashboard(self.guild_id, interaction.user, self.nonce)
            await interaction.followup.send(content=f"✅ {res.message}", ephemeral=True)
            await interaction.message.edit(view=new_view)
        else:
            await interaction.followup.send(content=f"❌ {res.message}", ephemeral=True)

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
            view, file = await handle_view_squad(interaction.guild_id, interaction.user.id, page=1)
            await interaction.edit_original_response(view=view, attachments=[file] if file else [])
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

        # Onboarding interactions are handled by registration_cog.py
        if custom_id_str.startswith("fcm:v1:onboarding:"):
            return

        logger.info(f"ui_interaction_received: custom_id={custom_id_str}, user_id={interaction.user.id}, guild_id={interaction.guild_id}")


        try:
            custom_id = decode_custom_id(custom_id_str)
        except ValueError as e:
            logger.warning(f"ui_custom_id_invalid: custom_id={custom_id_str}, error={e}")
            await self.send_error_response(interaction, "Invalid or unsupported interactive element.")
            return

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        nonce = custom_id.nonce

        # Ensure we are in a guild context unless it's a DM settings/admin action
        if not guild_id:
            if custom_id.scope not in ("dm_settings", "dm_admin", "nav", "schedule"):
                logger.warning(f"ui_interaction_rejected: reason=dm_not_allowed, user_id={user_id}")
                await self.send_error_response(interaction, "Interactive menus are not supported in DMs.")
                return
            # Fetch guild_id from session state for DM console
            session = ui_session_manager.get_session(nonce)
            if session:
                guild_id = session.guild_id
            else:
                guild_id = 0

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

            # Check if this is a public view action
            is_public_view = custom_id.scope in ("table", "fixtures", "match") or (custom_id.scope == "league" and custom_id.action in ("view_table", "refresh"))
            is_ephemeral_request = is_public_view and (interaction.guild_id is not None)

            # Defer response immediately to prevent 3-second Discord timeouts unless opening a modal
            is_opening_modal = (custom_id.scope == "dm_admin" and custom_id.action in ("extend_deadline", "open_modal")) or (custom_id.scope == "schedule" and custom_id.action == "open_modal")
            if not is_opening_modal:
                if is_ephemeral_request:
                    await interaction.response.defer(ephemeral=True)
                else:
                    await interaction.response.defer()

            # For public views, if session doesn't exist, is expired, or belongs to another user, create a temporary session
            if is_public_view:
                session = ui_session_manager.get_session(nonce)
                if not session or session.discord_user_id != user_id:
                    session = ui_session_manager.create_session(user_id, guild_id)
                    nonce = session.session_id

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

            elif custom_id.scope == "league":
                if custom_id.action == "join":
                    new_view = await handle_join_league(guild_id, interaction.user, nonce)
                elif custom_id.action == "start":
                    new_view = await handle_start_league(guild_id, interaction.user, nonce)
                elif custom_id.action == "refresh":
                    new_view = await handle_open_league_dashboard(guild_id, interaction.user, nonce)
                elif custom_id.action == "view_table":
                    new_view = await handle_view_table(guild_id, interaction.user, nonce)

            elif custom_id.scope == "table":
                if custom_id.action == "refresh":
                    new_view = await handle_refresh_table(guild_id, interaction.user, nonce)

            elif custom_id.scope == "fixtures":
                if custom_id.action == "view" and custom_id.target == "current":
                    new_view = await handle_view_current_week_fixtures(guild_id, interaction.user, nonce)
                elif custom_id.action == "week":
                    try:
                        target_week = int(custom_id.target)
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid week target in custom_id: {custom_id.target}")
                    new_view = await handle_view_week_fixtures(guild_id, interaction.user, nonce, target_week)
                elif custom_id.action == "refresh":
                    try:
                        refresh_week = int(custom_id.target)
                    except (ValueError, TypeError):
                        refresh_week = None
                    if refresh_week:
                        new_view = await handle_view_week_fixtures(guild_id, interaction.user, nonce, refresh_week)
                    else:
                        new_view = await handle_view_current_week_fixtures(guild_id, interaction.user, nonce)

            elif custom_id.scope == "matchday":
                if custom_id.action == "status":
                    new_view = await handle_view_matchday_status(guild_id, interaction.user, nonce)
                elif custom_id.action == "run":
                    new_view = await handle_run_matchday(guild_id, interaction.user, nonce)
                elif custom_id.action == "refresh":
                    new_view = await handle_view_matchday_status(guild_id, interaction.user, nonce)

            elif custom_id.scope == "match":
                if custom_id.action == "recent":
                    new_view = await handle_view_recent_match(guild_id, interaction.user, nonce)
                elif custom_id.action == "view":
                    new_view = await handle_view_match_detail(guild_id, interaction.user, custom_id.target, nonce)

            elif custom_id.scope == "dm_settings":
                from app.ui.handlers.dm_settings_handler import (
                    handle_open_settings_console,
                    handle_open_settings_overview,
                    handle_open_settings_channels,
                    handle_open_settings_admin_role,
                    handle_open_settings_automation,
                    handle_open_settings_schedule,
                    handle_open_settings_matchday,
                )
                from app.services.settings_service import SettingsService
                from app.ui.handlers.dm_admin_handler import handle_open_admin_dashboard

                session = ui_session_manager.get_session(nonce)

                if custom_id.action == "guild_select":
                    if not interaction.data.get("values"):
                        raise ValueError("No server selected.")
                    selected_guild_id = int(interaction.data["values"][0])
                    
                    if session:
                        session.guild_id = selected_guild_id
                        dest = session.metadata.get("dest", "settings")
                        if dest == "admin":
                            new_view = await handle_open_admin_dashboard(selected_guild_id, interaction.user, nonce)
                        else:
                            new_view = await handle_open_settings_overview(selected_guild_id, interaction.user, nonce)
                elif custom_id.action == "switch" and custom_id.target == "guild":
                    if session:
                        session.guild_id = 0
                    new_view = await handle_open_settings_console(interaction.user, nonce)
                elif custom_id.action == "view":
                    if custom_id.target == "overview":
                        new_view = await handle_open_settings_overview(guild_id, interaction.user, nonce)
                    elif custom_id.target == "channels":
                        new_view = await handle_open_settings_channels(guild_id, interaction.user, nonce)
                    elif custom_id.target == "admin_role":
                        new_view = await handle_open_settings_admin_role(guild_id, interaction.user, nonce)
                    elif custom_id.target == "automation":
                        new_view = await handle_open_settings_automation(guild_id, interaction.user, nonce)
                    elif custom_id.target == "schedule":
                        new_view = await handle_open_settings_schedule(guild_id, interaction.user, nonce)
                    elif custom_id.target == "matchday":
                        new_view = await handle_open_settings_matchday(guild_id, interaction.user, nonce)
                elif custom_id.action == "channel_game" and custom_id.target == "select":
                    if not interaction.data.get("values"):
                        raise ValueError("No channel selected.")
                    channel_id = interaction.data["values"][0]
                    guild_obj = self.bot.get_guild(guild_id) if self.bot else None
                    await SettingsService.update_channels(guild_id, guild_obj, game_channel_id=channel_id)
                    new_view = await handle_open_settings_channels(guild_id, interaction.user, nonce)
                elif custom_id.action == "channel_match" and custom_id.target == "select":
                    if not interaction.data.get("values"):
                        raise ValueError("No channel selected.")
                    channel_id = interaction.data["values"][0]
                    guild_obj = self.bot.get_guild(guild_id) if self.bot else None
                    await SettingsService.update_channels(guild_id, guild_obj, matchday_channel_id=channel_id)
                    new_view = await handle_open_settings_channels(guild_id, interaction.user, nonce)
                elif custom_id.action == "role_admin" and custom_id.target == "select":
                    if not interaction.data.get("values"):
                        raise ValueError("No role selected.")
                    role_id = interaction.data["values"][0]
                    # Check clear option
                    val = None if role_id == "clear" else role_id
                    await SettingsService.update_admin_role(guild_id, val)
                    new_view = await handle_open_settings_admin_role(guild_id, interaction.user, nonce)

            elif custom_id.scope == "schedule":
                from app.services.settings_service import SettingsService
                from app.ui.handlers.dm_settings_handler import handle_open_settings_schedule
                guild_obj = interaction.guild or (self.bot.get_guild(guild_id) if self.bot else None)
                if custom_id.action == "enable":
                    await SettingsService.enable_schedule(guild_id, guild_obj)
                    new_view = await handle_open_settings_schedule(guild_id, interaction.user, nonce)
                elif custom_id.action == "disable":
                    await SettingsService.disable_schedule(guild_id)
                    new_view = await handle_open_settings_schedule(guild_id, interaction.user, nonce)
                elif custom_id.action == "open_modal":
                    modal = ScheduleSetupModal(guild_id, nonce, self.bot)
                    await interaction.response.send_modal(modal)
                    return
                elif custom_id.action == "refresh":
                    new_view = await handle_open_settings_schedule(guild_id, interaction.user, nonce)

            elif custom_id.scope == "dm_admin":
                from app.ui.handlers.dm_admin_handler import handle_open_admin_dashboard
                
                # Check permissions first for any admin action
                from app.services.permission_service import can_run_admin_action
                is_admin = await can_run_admin_action(guild_id, user_id)
                if not is_admin:
                    if custom_id.action == "extend_deadline":
                        await interaction.response.send_message("❌ You do not have administrator permissions in that server.", ephemeral=True)
                    else:
                        await self.send_error_response(interaction, "You do not have administrator permissions.")
                    return

                if custom_id.action == "extend_deadline":
                    modal = ExtendDeadlineModal(guild_id, nonce, self.bot)
                    await interaction.response.send_modal(modal)
                    return
                elif custom_id.action == "open_modal" and custom_id.target == "create_league":
                    modal = CreateLeagueModal(guild_id, nonce, self.bot)
                    await interaction.response.send_modal(modal)
                    return
                elif custom_id.action == "cancel_league":
                    from app.services.league_service import cancel_league
                    res = await cancel_league(guild_id)
                    new_view = await handle_open_admin_dashboard(guild_id, interaction.user, nonce)
                    if res.success:
                        await interaction.followup.send(content=f"✅ {res.message}", ephemeral=True)
                    else:
                        await interaction.followup.send(content=f"❌ {res.message}", ephemeral=True)
                elif custom_id.action == "matchday_run":
                    from app.services.matchday_service import MatchdayService
                    from app.services.announcement_service import AnnouncementService
                    from app.db.session import get_session
                    # Get current week
                    async with get_session() as db_sess:
                        from app.repositories.league_repository import get_active_league_by_guild
                        from app.repositories.season_repository import get_active_season_for_league
                        league = await get_active_league_by_guild(db_sess, guild_id)
                        season = await get_active_season_for_league(db_sess, guild_id, league.id) if league else None
                        week = season.current_week if season else 1
                        
                    bot_user_id = self.bot.user.id if self.bot and self.bot.user else 0
                    res = await MatchdayService.run_current_matchday(guild_id, bot_user_id, is_admin=True)
                    if res.success:
                        AnnouncementService.bot = self.bot
                        await AnnouncementService.announce_matchday_summary(guild_id, week, res.results)
                        if res.season_completed:
                            await AnnouncementService.announce_season_complete(guild_id, res.season_number, res.winner_name)
                    new_view = await handle_open_admin_dashboard(guild_id, interaction.user, nonce)
                elif custom_id.action == "automation_check":
                    from app.services.game_loop_orchestrator import GameLoopOrchestrator
                    orchestrator = GameLoopOrchestrator(self.bot)
                    await orchestrator.run_guild_check(guild_id)
                    new_view = await handle_open_admin_dashboard(guild_id, interaction.user, nonce)
                elif custom_id.action == "league_start":
                    from app.services.league_service import start_league
                    from app.services.announcement_service import AnnouncementService
                    res = await start_league(guild_id)
                    if res.success:
                        AnnouncementService.bot = self.bot
                        await AnnouncementService.announce_league_start(guild_id, res.league_name)
                    new_view = await handle_open_admin_dashboard(guild_id, interaction.user, nonce)
                elif custom_id.action in ("refresh", "view"):
                    new_view = await handle_open_admin_dashboard(guild_id, interaction.user, nonce)

            elif custom_id.scope == "nav" and custom_id.action == "back":

                if custom_id.target == "locker":
                    new_view = await handle_open_locker_room(guild_id, user_id, nonce)
                elif custom_id.target == "squad":
                    session = ui_session_manager.get_session(nonce)
                    page = session.metadata.get("squad_page", 1) if session else 1
                    new_view = await handle_view_squad(guild_id, user_id, page=page, nonce=nonce)
                elif custom_id.target == "league":
                    new_view = await handle_open_league_dashboard(guild_id, interaction.user, nonce)

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

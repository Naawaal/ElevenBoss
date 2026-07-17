# apps/discord_bot/cogs/admin_cog.py
from __future__ import annotations
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.cogs.league_cog import fetch_standings, auto_sim_expired_fixtures, BOT_NAMES

logger = logging.getLogger(__name__)


async def _latest_season(
    db,
    league_id: str,
    status: str,
) -> dict | None:
    """Newest season for status — avoids maybe_single 406 when duplicates exist."""
    res = await (
        db.table("league_seasons")
        .select("*")
        .eq("league_id", league_id)
        .eq("status", status)
        .order("season_number", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


async def is_owner(interaction: discord.Interaction) -> bool:
    """Verifies that the invoking user is the bot owner."""
    return await interaction.client.is_owner(interaction.user)

async def show_guild_select(interaction: discord.Interaction, owner_id: int):
    """Shows the server selection dropdown."""
    mutual_admin_guilds = []
    for guild in interaction.client.guilds:
        member = guild.get_member(owner_id)
        if member and member.guild_permissions.administrator:
            mutual_admin_guilds.append(guild)

    if not mutual_admin_guilds:
        embed = error_embed("No mutual servers found where you are an Administrator.")
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="🛠️ ElevenBoss Administrator Panel",
        description="Select a server below to manage league configurations:",
        color=0x00FF87
    )
    view = GuildSelectView(owner_id, mutual_admin_guilds)
    if interaction.response.is_done():
        msg = await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)
        msg = await interaction.original_response()
    view.message = msg

async def show_admin_hub(interaction: discord.Interaction, guild_id: int, owner_id: int):
    """Shows the central Admin Panel options for a selected server."""
    guild = interaction.client.get_guild(guild_id)
    if not guild:
        return

    db = await get_client()
    res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
    config = res.data if res else None
    if not config:
        await db.table("guild_config").insert({"guild_id": guild_id}).execute()
        res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
        config = res.data if res else None

    channel_id = config.get("league_channel_id")
    role_id = config.get("announcement_role_id")
    channel_obj = guild.get_channel(channel_id) if channel_id else None
    role_obj = guild.get_role(role_id) if role_id else None

    channel_str = f"#{channel_obj.name}" if channel_obj else ("Not Set" if not channel_id else f"Unknown Channel (ID: {channel_id})")
    role_str = f"@{role_obj.name}" if role_obj else ("Not Set" if not role_id else f"Unknown Role (ID: {role_id})")

    embed = discord.Embed(
        title=f"🛠️ ElevenBoss Admin Panel",
        description=f"Managing settings for server: **{guild.name}**",
        color=0x00FF87
    )
    embed.add_field(name="📢 League announce channel", value=channel_str, inline=True)
    embed.add_field(name="🎖️ League mention role", value=role_str, inline=True)
    embed.add_field(name="🏆 League Status", value=config.get("league_status", "inactive").upper(), inline=False)
    err = config.get("automation_last_error")
    if err:
        embed.add_field(name="⚠️ Automation last error", value=str(err)[:1024], inline=False)

    view = AdminHubView(owner_id, guild_id)
    if interaction.response.is_done():
        msg = await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)
        msg = await interaction.original_response()
    view.message = msg

async def show_announcements_menu(interaction: discord.Interaction, guild_id: int, owner_id: int):
    """Shows the announcement channel/role config menu."""
    guild = interaction.client.get_guild(guild_id)
    if not guild:
        return

    db = await get_client()
    res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
    config = res.data if res else None
    if not config:
        config = {}

    channel_id = config.get("league_channel_id")
    role_id = config.get("announcement_role_id")
    channel_obj = guild.get_channel(channel_id) if channel_id else None
    role_obj = guild.get_role(role_id) if role_id else None

    channel_str = f"#{channel_obj.name}" if channel_obj else ("Not Set" if not channel_id else f"Unknown Channel (ID: {channel_id})")
    role_str = f"@{role_obj.name}" if role_obj else ("Not Set" if not role_id else f"Unknown Role (ID: {role_id})")

    embed = discord.Embed(
        title=f"📢 Announcement Settings - {guild.name}",
        description="Configure the league announce channel and mention role for Digests / registration pings.",
        color=0x00FF87
    )
    embed.add_field(name="League announce channel", value=channel_str, inline=True)
    embed.add_field(name="League mention role", value=role_str, inline=True)
    err = config.get("automation_last_error")
    if err:
        embed.add_field(name="⚠️ Automation last error", value=str(err)[:1024], inline=False)

    view = AnnouncementSubView(owner_id, guild_id)
    if interaction.response.is_done():
        msg = await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)
        msg = await interaction.original_response()
    view.message = msg


async def show_league_management(interaction: discord.Interaction, guild_id: int, owner_id: int):
    """Shows the admin League Management sub-menu."""
    guild = interaction.client.get_guild(guild_id)
    if not guild:
        return

    db = await get_client()
    league_res = await db.table("leagues").select("*").eq("guild_id", guild_id).maybe_single().execute()
    league = league_res.data if league_res else None

    season = None
    reg_season = None
    paused_season = None
    paused_count = 0
    if league:
        season = await _latest_season(db, league["id"], "active")
        if not season:
            paused_rows = await (
                db.table("league_seasons")
                .select("id")
                .eq("league_id", league["id"])
                .eq("status", "paused")
                .execute()
            )
            paused_count = len(paused_rows.data or [])
            paused_season = await _latest_season(db, league["id"], "paused")
        if not season and not paused_season:
            reg_season = await _latest_season(db, league["id"], "registration")

    # Fetch registered league members count
    regs_res = await db.table("league_members").select("player_id", count="exact").eq("guild_id", guild_id).execute()
    reg_count = regs_res.count if regs_res else 0

    embed = discord.Embed(
        title=f"🏆 League Management — {guild.name}",
        description="Manage server-specific seasonal league operations below:",
        color=0x00FF87
    )
    from apps.discord_bot.core.economy_rpc import guild_automation_effective

    automation_on = await guild_automation_effective(db, guild_id)
    live_season = season or paused_season

    embed.add_field(name="Registered Managers", value=f"**{reg_count}**", inline=True)
    if live_season:
        status_label = "Paused" if paused_season else "Yes"
        season_label = f"{status_label} (Season #{live_season['season_number']})"
        if paused_count > 1:
            season_label += f" — **{paused_count} paused** (Force End clears newest first)"
        embed.add_field(
            name="Active Season",
            value=season_label,
            inline=True,
        )
        embed.add_field(
            name="Matchday",
            value=f"{live_season['current_matchday']} / {live_season['total_matchdays']}",
            inline=True,
        )
        embed.add_field(name="Duration Set", value=f"{live_season['duration_days']} days", inline=True)
        cfg = live_season.get("config_json") or {}
        if cfg:
            embed.add_field(name="Config", value=f"Size **{cfg.get('max_clubs', 8)}** | OVR cap **{cfg.get('ovr_cap') or 'none'}**", inline=False)
    elif reg_season:
        embed.add_field(name="Status", value=f"📝 Registration (Season #{reg_season['season_number']})", inline=True)
        cfg = reg_season.get("config_json") or {}
        embed.add_field(name="Target Size", value=str(cfg.get("max_clubs", 8)), inline=True)
    else:
        embed.add_field(name="Active Season", value="No", inline=True)

    if automation_on:
        embed.set_footer(
            text="Lifecycle is automated. Pause / Force End for emergencies. "
            "Run League Cycle Now = same as 00:05 UTC tick (pilot)."
        )

    view = LeagueManagementView(
        owner_id,
        guild_id,
        has_active_season=live_season is not None,
        has_registration=reg_season is not None,
        automation_effective=automation_on,
    )
    if interaction.response.is_done():
        msg = await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)
        msg = await interaction.original_response()
    view.message = msg


# --- VIEWS ---

class BaseAdminView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This admin panel is private.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                embed = self.message.embeds[0]
                embed.set_footer(text="Session timed out. Run /admin to restart.")
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

class GuildSelectView(BaseAdminView):
    def __init__(self, owner_id: int, guilds: list[discord.Guild]) -> None:
        super().__init__(owner_id)
        
        options = []
        for g in guilds[:25]:
            options.append(
                discord.SelectOption(
                    label=g.name,
                    description=f"ID: {g.id}",
                    value=str(g.id)
                )
            )

        select = discord.ui.Select(placeholder="Choose a server to configure...", options=options)
        select.callback = self.guild_select_callback
        self.add_item(select)

    async def guild_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = int(interaction.data["values"][0])
        await show_admin_hub(interaction, guild_id, self.owner_id)

class AdminHubView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

    @discord.ui.button(style=discord.ButtonStyle.primary, label="📢 Announcements", custom_id="admin_hub_announce", row=0)
    async def announce_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🏆 League Management", custom_id="admin_hub_league", row=0)
    async def league_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_league_management(interaction, self.guild_id, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🔄 Switch Server", custom_id="admin_hub_switch", row=1)
    async def switch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_guild_select(interaction, self.owner_id)

class AnnouncementSubView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

    @discord.ui.button(style=discord.ButtonStyle.primary, label="League announce channel", custom_id="announce_set_channel")
    async def channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = ChannelSelectView(self.owner_id, self.guild_id, guild)
        embed = discord.Embed(
            title="📢 League announce channel",
            description="Choose the text channel for league digests and registration pings:",
            color=0x00FF87,
        )
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    @discord.ui.button(style=discord.ButtonStyle.primary, label="League mention role", custom_id="announce_set_role")
    async def role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = RoleSelectView(self.owner_id, self.guild_id, guild)
        embed = discord.Embed(
            title="📢 League mention role",
            description="Choose the role pinged for league announcements:",
            color=0x00FF87,
        )
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Admin Hub", custom_id="announce_back_hub")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_admin_hub(interaction, self.guild_id, self.owner_id)

class ChannelSearchModal(discord.ui.Modal, title="Configure Channel"):
    input_text = discord.ui.TextInput(
        label="Channel Name or ID",
        placeholder="e.g. announcements or 123456789...",
        required=True
    )

    def __init__(self, owner_id: int, guild_id: int, view: ChannelSelectView):
        super().__init__()
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        text = self.input_text.value.strip()
        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send(embed=error_embed("Server not found."), ephemeral=True)
            return

        channel = None
        if text.isdigit():
            channel = guild.get_channel(int(text))
        
        if not channel:
            channel = next((c for c in guild.text_channels if c.name.lower() == text.lower() or c.name.lower() == text.lower().lstrip('#')), None)

        if not channel:
            await interaction.followup.send(embed=error_embed(f"No text channel found matching '{text}'."), ephemeral=True)
            return

        permissions = channel.permissions_for(guild.me)
        if not (permissions.view_channel and permissions.send_messages):
            await interaction.followup.send(embed=error_embed(f"Bot lacks permissions to view/send messages in {channel.mention}."), ephemeral=True)
            return

        db = await get_client()
        await db.table("guild_config").update({"league_channel_id": channel.id}).eq("guild_id", self.guild_id).execute()

        await interaction.followup.send(f"✅ Announcement channel updated to {channel.mention}.", ephemeral=True)
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

class RoleSearchModal(discord.ui.Modal, title="Configure Role"):
    input_text = discord.ui.TextInput(
        label="Role Name or ID",
        placeholder="e.g. Member or 123456789...",
        required=True
    )

    def __init__(self, owner_id: int, guild_id: int, view: RoleSelectView):
        super().__init__()
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        text = self.input_text.value.strip()
        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send(embed=error_embed("Server not found."), ephemeral=True)
            return

        role = None
        if text.isdigit():
            role = guild.get_role(int(text))
        
        if not role:
            role = next((r for r in guild.roles if r.name.lower() == text.lower()), None)

        if not role:
            await interaction.followup.send(embed=error_embed(f"No role found matching '{text}'."), ephemeral=True)
            return

        db = await get_client()
        await db.table("guild_config").update({"announcement_role_id": role.id}).eq("guild_id", self.guild_id).execute()

        await interaction.followup.send(f"✅ Announcement role updated to **{role.name}**.", ephemeral=True)
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

class ChannelSelectView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int, guild: discord.Guild | None, page: int = 0) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id
        self.page = page

        eligible_channels = []
        if guild:
            for channel in guild.text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.view_channel and permissions.send_messages:
                    eligible_channels.append(channel)

        total_channels = len(eligible_channels)
        start = page * 25
        end = start + 25
        page_channels = eligible_channels[start:end]

        options = []
        for channel in page_channels:
            options.append(
                discord.SelectOption(
                    label=f"#{channel.name}",
                    value=str(channel.id),
                    description=f"ID: {channel.id}"
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No eligible channels found" if page == 0 else "No more channels on this page",
                    value="none",
                    description="Make sure the bot has permissions in text channels." if page == 0 else "Go back to the previous page."
                )
            )

        total_pages = (total_channels - 1) // 25 + 1 if total_channels > 0 else 1
        select = discord.ui.Select(
            placeholder=f"Select Announcement Channel (Page {page + 1}/{total_pages})...",
            options=options
        )
        select.callback = self.channel_select_callback
        self.add_item(select)

        # Pagination navigation
        if page > 0:
            prev_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Prev Page", row=1)
            prev_btn.callback = self.prev_page_callback
            self.add_item(prev_btn)

        if end < total_channels:
            next_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Next Page ➡️", row=1)
            next_btn.callback = self.next_page_callback
            self.add_item(next_btn)

        search_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="🔍 Enter Name/ID", row=1)
        search_btn.callback = self.search_callback
        self.add_item(search_btn)

        cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Cancel", row=1)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def prev_page_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = ChannelSelectView(self.owner_id, self.guild_id, guild, page=self.page - 1)
        embed = discord.Embed(title="📢 Configure Channel", description="Choose the text channel for announcements:", color=0x00FF87)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    async def next_page_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = ChannelSelectView(self.owner_id, self.guild_id, guild, page=self.page + 1)
        embed = discord.Embed(title="📢 Configure Channel", description="Choose the text channel for announcements:", color=0x00FF87)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    async def search_callback(self, interaction: discord.Interaction):
        modal = ChannelSearchModal(self.owner_id, self.guild_id, self)
        await interaction.response.send_modal(modal)

    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

    async def channel_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        val = interaction.data["values"][0]
        if val == "none":
            await interaction.followup.send(embed=error_embed("No channel selected."), ephemeral=True)
            return

        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send(embed=error_embed("Server not found."), ephemeral=True)
            return

        channel_id = int(val)
        channel = guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send(embed=error_embed("Selected channel is not in the active server."), ephemeral=True)
            return

        db = await get_client()
        await db.table("guild_config").update({"league_channel_id": channel_id}).eq("guild_id", self.guild_id).execute()

        await interaction.followup.send(f"✅ Announcement channel updated to {channel.mention}.", ephemeral=True)
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

class RoleSelectView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int, guild: discord.Guild | None, page: int = 0) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id
        self.page = page

        roles = []
        if guild:
            roles = [r for r in guild.roles if not r.is_default()]
            roles.reverse()  # Show highest-positioned roles first

        total_roles = len(roles)
        start = page * 25
        end = start + 25
        page_roles = roles[start:end]

        options = []
        for role in page_roles:
            options.append(
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"ID: {role.id}"
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No roles found" if page == 0 else "No more roles on this page",
                    value="none",
                    description="Create a role in the server first." if page == 0 else "Go back to the previous page."
                )
            )

        total_pages = (total_roles - 1) // 25 + 1 if total_roles > 0 else 1
        select = discord.ui.Select(
            placeholder=f"Select Announcement Role (Page {page + 1}/{total_pages})...",
            options=options
        )
        select.callback = self.role_select_callback
        self.add_item(select)

        # Pagination navigation
        if page > 0:
            prev_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Prev Page", row=1)
            prev_btn.callback = self.prev_page_callback
            self.add_item(prev_btn)

        if end < total_roles:
            next_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Next Page ➡️", row=1)
            next_btn.callback = self.next_page_callback
            self.add_item(next_btn)

        search_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="🔍 Enter Name/ID", row=1)
        search_btn.callback = self.search_callback
        self.add_item(search_btn)

        cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Cancel", row=1)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def prev_page_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = RoleSelectView(self.owner_id, self.guild_id, guild, page=self.page - 1)
        embed = discord.Embed(title="📢 Configure Role", description="Choose the target role for announcement mentions:", color=0x00FF87)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    async def next_page_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = RoleSelectView(self.owner_id, self.guild_id, guild, page=self.page + 1)
        embed = discord.Embed(title="📢 Configure Role", description="Choose the target role for announcement mentions:", color=0x00FF87)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    async def search_callback(self, interaction: discord.Interaction):
        modal = RoleSearchModal(self.owner_id, self.guild_id, self)
        await interaction.response.send_modal(modal)

    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

    async def role_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        val = interaction.data["values"][0]
        if val == "none":
            await interaction.followup.send(embed=error_embed("No role selected."), ephemeral=True)
            return

        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send(embed=error_embed("Server not found."), ephemeral=True)
            return

        role_id = int(val)
        role = guild.get_role(role_id)
        if not role:
            await interaction.followup.send(embed=error_embed("Selected role is not in the active server."), ephemeral=True)
            return

        db = await get_client()
        await db.table("guild_config").update({"announcement_role_id": role_id}).eq("guild_id", self.guild_id).execute()

        await interaction.followup.send(f"✅ Announcement role updated to **{role.name}**.", ephemeral=True)
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)


class LeagueManagementView(BaseAdminView):
    def __init__(
        self,
        owner_id: int,
        guild_id: int,
        has_active_season: bool,
        has_registration: bool = False,
        automation_effective: bool = False,
    ) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

        def _drop(item: discord.ui.Item) -> None:
            try:
                self.remove_item(item)
            except ValueError:
                pass

        if automation_effective:
            _drop(self.start_btn)
            _drop(self.open_reg_btn)
            _drop(self.config_btn)
            _drop(self.kick_btn)
            _drop(self.force_sim_btn)
            _drop(self.duration_btn)
        else:
            # ponytail: pilot-only Run Cycle — remove once 00:05 cron is validated on prod
            _drop(self.run_cycle_btn)

        if has_active_season:
            if not automation_effective:
                _drop(self.start_btn)
                _drop(self.open_reg_btn)
                _drop(self.config_btn)
        else:
            _drop(self.end_btn)
            if not automation_effective:
                _drop(self.kick_btn)
                _drop(self.force_sim_btn)
                _drop(self.duration_btn)
            _drop(self.pause_btn)
            if not automation_effective:
                if has_registration:
                    _drop(self.open_reg_btn)
                else:
                    _drop(self.config_btn)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="📝 Open Registration", custom_id="league_admin_open_reg", row=0)
    async def open_reg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await admin_open_registration(interaction, self.guild_id, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⚙️ Configure Season", custom_id="league_admin_config", row=0)
    async def config_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await admin_season_config_modal(interaction, self)

    @discord.ui.button(style=discord.ButtonStyle.success, label="🚀 Start Season", custom_id="league_admin_start", row=0)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await admin_start_season(interaction, self.guild_id, self.owner_id, self)

    @discord.ui.button(style=discord.ButtonStyle.danger, label="⏹️ Force End Season", custom_id="league_admin_end", row=0)
    async def end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await admin_end_season(interaction, self.guild_id, self.owner_id, self)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🥾 Kick Manager", custom_id="league_admin_kick", row=1)
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await admin_kick_menu(interaction, self.guild_id, self.owner_id, self)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🎲 Force-Sim Matchday", custom_id="league_admin_sim", row=1)
    async def force_sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await admin_force_sim(interaction, self.guild_id, self.owner_id, self)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⏱️ Set Duration", custom_id="league_admin_duration", row=1)
    async def duration_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await admin_duration_modal(interaction, self)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⏸️ Pause / Resume", custom_id="league_admin_pause", row=1)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await admin_toggle_pause(interaction, self.guild_id, self.owner_id)

    # ponytail: pilot-only — remove after midnight cron is trusted on prod
    @discord.ui.button(
        style=discord.ButtonStyle.primary,
        label="⚡ Run League Cycle Now",
        custom_id="league_admin_run_cycle",
        row=2,
    )
    async def run_cycle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await admin_run_league_cycle(interaction, self.guild_id, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Admin Hub", custom_id="league_admin_back", row=2)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_admin_hub(interaction, self.guild_id, self.owner_id)


class KickManagerSelectView(BaseAdminView):
    def __init__(self, owner_id: int, parent_view: LeagueManagementView, standings: list[dict]) -> None:
        super().__init__(owner_id)
        self.parent_view = parent_view

        options = []
        for row in standings:
            if not row.get("is_ai") and row.get("is_active"):
                options.append(
                    discord.SelectOption(
                        label=f"{row['club_name']} ({row['username']})",
                        value=str(row["discord_id"]),
                        description=f"GD: {row['goal_difference']}, PTS: {row['points']}"
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No active human managers",
                    value="none",
                    description="No human manager can be kicked right now."
                )
            )

        select = discord.ui.Select(placeholder="Select manager to kick...", options=options)
        select.callback = self.kick_select_callback
        self.add_item(select)

        cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Cancel")
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await show_league_management(interaction, self.parent_view.guild_id, self.owner_id)

    async def kick_select_callback(self, interaction: discord.Interaction):
        val = interaction.data["values"][0]
        if val == "none":
            await interaction.response.send_message("No manager selected.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        kicked_id = int(val)
        await admin_execute_kick(interaction, kicked_id, self.parent_view.guild_id, self.owner_id, self.parent_view)


class SeasonConfigModal(discord.ui.Modal, title="Configure League Season"):
    max_clubs = discord.ui.TextInput(label="Max clubs (8, 12, or 16)", default="8", max_length=2)
    duration_days = discord.ui.TextInput(label="Season duration (days)", default="28", max_length=3)
    ovr_cap = discord.ui.TextInput(label="OVR cap (optional)", required=False, placeholder="e.g. 75", max_length=3)
    entry_fee = discord.ui.TextInput(label="Entry fee coins (0=free)", default="0", max_length=5)

    def __init__(self, view: LeagueManagementView, *, duration_default: int = 28) -> None:
        super().__init__()
        self.admin_view = view
        self.duration_days.default = str(duration_default)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            size = int(self.max_clubs.value)
            if size not in (8, 12, 16):
                raise ValueError("size")
            days = int(self.duration_days.value)
            fee = int(self.entry_fee.value or "0")
            cap = int(self.ovr_cap.value) if self.ovr_cap.value.strip() else None
        except ValueError:
            await interaction.followup.send(embed=error_embed("Invalid config values."), ephemeral=True)
            return
        await admin_save_season_config(interaction, self.admin_view.guild_id, {
            "max_clubs": size,
            "duration_days": days,
            "ovr_cap": cap,
            "entry_fee_coins": fee,
            "bot_fill": True,
        })


class DurationModal(discord.ui.Modal, title="Set Season Duration"):
    days = discord.ui.TextInput(
        label="Duration (in days)",
        placeholder="e.g. 7",
        default="7",
        min_length=1,
        max_length=3
    )

    def __init__(self, view: LeagueManagementView) -> None:
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            val = int(self.days.value)
            if val <= 0:
                raise ValueError()
        except ValueError:
            await interaction.followup.send(embed=error_embed("Duration must be a positive integer."), ephemeral=True)
            return

        await admin_execute_set_duration(interaction, val, self.view.guild_id, self.view.owner_id, self.view)


# --- LEAGUE ADMIN HELPER FUNCTIONS ---

async def _next_ai_discord_id(db) -> int:
    min_p_res = await db.table("players").select("discord_id").order("discord_id", desc=False).limit(1).execute()
    current_min = min_p_res.data[0]["discord_id"] if min_p_res.data else 0
    if current_min > 0:
        current_min = 0
    return current_min - 1


async def _insert_ai_club(db, *, used_names: set[str], ai_id: int) -> dict:
    available = [n for n in BOT_NAMES if n not in used_names] or list(BOT_NAMES)
    bot_name = random.choice(available)
    used_names.add(bot_name)
    ai_p = {
        "discord_id": ai_id,
        "username": bot_name,
        "club_name": bot_name,
        "manager_name": "AI Coach",
        "is_ai": True,
        "ai_rating": 60.0,
    }
    await db.table("players").insert(ai_p).execute()
    return ai_p


async def admin_open_registration(interaction: discord.Interaction, guild_id: int, owner_id: int):
    db = await get_client()
    from apps.discord_bot.core.economy_rpc import guild_automation_effective

    if await guild_automation_effective(db, guild_id):
        await interaction.followup.send(
            embed=error_embed(
                "League automation is active for this server — registration opens automatically. "
                "Use Pause / Force End for emergencies."
            ),
            ephemeral=True,
        )
        return

    guild = interaction.client.get_guild(guild_id)
    await db.table("leagues").upsert({"guild_id": guild_id, "name": guild.name if guild else "League"}, on_conflict="guild_id").execute()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    league_id = league_res.data["id"]

    existing = await db.table("league_seasons").select("id").eq("league_id", league_id).in_("status", ["active", "registration"]).execute()
    if existing.data:
        await interaction.followup.send(embed=error_embed("A season is already active or in registration."), ephemeral=True)
        return

    from apps.discord_bot.core.economy_rpc import league_dynamics_enabled
    dynamics = await league_dynamics_enabled(db)
    duration_days = 14 if dynamics else 28

    seasons_res = await db.table("league_seasons").select("season_number").eq("league_id", league_id).order("season_number", desc=True).limit(1).execute()
    next_num = (seasons_res.data[0]["season_number"] + 1) if seasons_res.data else 1
    reg_hours = 72
    deadline = datetime.now(timezone.utc) + timedelta(hours=reg_hours)

    await db.table("league_seasons").insert({
        "league_id": league_id,
        "season_number": next_num,
        "status": "registration",
        "current_matchday": 0,
        "total_matchdays": 0,
        "duration_days": duration_days,
        "end_time": deadline.isoformat(),
        "config_json": {
            "max_clubs": 8,
            "duration_days": duration_days,
            "bot_fill": True,
            "entry_fee_coins": 0,
        },
    }).execute()
    await interaction.followup.send(embed=success_embed(f"📝 Registration open for Season #{next_num}. Closes <t:{int(deadline.timestamp())}:R>."))
    await show_league_management(interaction, guild_id, owner_id)


async def admin_save_season_config(interaction: discord.Interaction, guild_id: int, config: dict):
    db = await get_client()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        await interaction.followup.send(embed=error_embed("No league found."), ephemeral=True)
        return
    season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "registration").maybe_single().execute()
    if not season_res or not season_res.data:
        await interaction.followup.send(embed=error_embed("Open registration first."), ephemeral=True)
        return
    await db.table("league_seasons").update({
        "config_json": config,
        "duration_days": config.get("duration_days", 28),
    }).eq("id", season_res.data["id"]).execute()
    await interaction.followup.send(embed=success_embed("⚙️ Season configuration saved."))


async def admin_season_config_modal(interaction: discord.Interaction, view: LeagueManagementView):
    from apps.discord_bot.core.economy_rpc import league_dynamics_enabled
    db = await get_client()
    dynamics = await league_dynamics_enabled(db)
    await interaction.response.send_modal(
        SeasonConfigModal(view, duration_default=14 if dynamics else 28)
    )


async def admin_toggle_pause(interaction: discord.Interaction, guild_id: int, owner_id: int):
    db = await get_client()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        return
    season = await _latest_season(db, league_res.data["id"], "active")
    if not season:
        season = await _latest_season(db, league_res.data["id"], "paused")
    if not season:
        await interaction.followup.send(embed=error_embed("No active/paused season."), ephemeral=True)
        return
    new_status = "paused" if season["status"] == "active" else "active"
    await db.table("league_seasons").update({"status": new_status}).eq("id", season["id"]).execute()
    await interaction.followup.send(embed=success_embed(f"Season {'paused' if new_status == 'paused' else 'resumed'}."))
    await show_league_management(interaction, guild_id, owner_id)


async def admin_run_league_cycle(interaction: discord.Interaction, guild_id: int, owner_id: int):
    """Pilot: manually invoke the 00:05 UTC state machine for this bot process."""
    from apps.discord_bot.core.economy_rpc import guild_automation_effective
    from apps.discord_bot.core.league_automation import run_league_state_machine

    db = await get_client()
    if not await guild_automation_effective(db, guild_id):
        await interaction.followup.send(
            embed=error_embed("League automation is not effective for this server."),
            ephemeral=True,
        )
        return

    bot = interaction.client
    await interaction.followup.send(
        embed=success_embed("Running league cycle (same as 00:05 UTC tick)…"),
        ephemeral=True,
    )
    try:
        await run_league_state_machine(bot)
    except Exception:
        logger.exception("Manual league cycle failed guild=%s", guild_id)
        await interaction.followup.send(
            embed=error_embed("League cycle failed — check bot logs."),
            ephemeral=True,
        )
        return

    cfg = await (
        db.table("guild_config")
        .select("automation_last_error")
        .eq("guild_id", guild_id)
        .maybe_single()
        .execute()
    )
    err = (cfg.data or {}).get("automation_last_error") if cfg else None
    if err:
        await interaction.followup.send(
            embed=error_embed(f"Cycle finished with automation error:\n`{err}`"),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            embed=success_embed(
                "Cycle finished. Check the league announce channel — "
                "if nothing opened, Force End leftover registration/paused seasons first."
            ),
            ephemeral=True,
        )
    await show_league_management(interaction, guild_id, owner_id)


async def admin_start_season(interaction: discord.Interaction, guild_id: int, owner_id: int, view: LeagueManagementView):
    """Thin wrapper — core start lives in ``league_automation.start_dynamics_season_from_registration``."""
    db = await get_client()
    from apps.discord_bot.core.economy_rpc import guild_automation_effective
    from apps.discord_bot.core.league_automation import start_dynamics_season_from_registration

    if await guild_automation_effective(db, guild_id):
        await interaction.followup.send(
            embed=error_embed(
                "League automation is active for this server — seasons start automatically when registration closes. "
                "Use Pause / Force End for emergencies."
            ),
            ephemeral=True,
        )
        return

    guild = interaction.client.get_guild(guild_id)
    if not guild:
        return

    result = await start_dynamics_season_from_registration(
        interaction.client,
        db,
        guild,
        automation=False,
        interaction=interaction,
    )
    if not result.get("ok"):
        await interaction.followup.send(
            embed=error_embed(result.get("error") or "Failed to start season."),
            ephemeral=True,
        )
        return

    await interaction.followup.send(embed=success_embed(result.get("success_body") or "Season started."))
    await show_league_management(interaction, guild_id, owner_id)


async def admin_end_season(interaction: discord.Interaction, guild_id: int, owner_id: int, view: LeagueManagementView):
    db = await get_client()
    guild = interaction.client.get_guild(guild_id)
    if not guild:
        return

    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        await interaction.followup.send(embed=error_embed("No league found for this server."), ephemeral=True)
        return

    league_id = league_res.data["id"]
    season = await _latest_season(db, league_id, "active")
    if not season:
        season = await _latest_season(db, league_id, "paused")
    if not season:
        # Allow Force End to clear a stuck registration-only state
        season = await _latest_season(db, league_id, "registration")
    if not season:
        await interaction.followup.send(embed=error_embed("No active/paused/registration season to end."), ephemeral=True)
        return

    stuck = await (
        db.table("league_seasons")
        .select("id, season_number, status")
        .eq("league_id", league_id)
        .in_("status", ["active", "paused", "registration"])
        .execute()
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    ended_ids = []
    for row in stuck.data or []:
        await db.table("league_seasons").update({
            "status": "completed",
            "end_time": now_iso,
        }).eq("id", row["id"]).execute()
        ended_ids.append(row["id"])

    if season["status"] != "registration":
        try:
            prize_res = await db.rpc("distribute_season_prizes", {"p_season_id": season["id"]}).execute()
            logger.info("Season prizes distributed: %s", prize_res.data)
        except Exception:
            logger.exception("distribute_season_prizes failed for season %s", season["id"])

    config_res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
    config = config_res.data if config_res else None

    league_updates_thread_id = config.get("league_updates_thread_id") if config else None
    chan_id = config.get("league_channel_id") if config else None

    guild_config_update: dict = {"league_status": "inactive"}
    if season.get("thread_format") != "dual_v2" and league_updates_thread_id:
        guild_config_update["league_updates_thread_id"] = None
    # E10: when automation owns the guild, Force End must not allow same-day re-open —
    # schedule next Monday 00:05 UTC like under-min registration failures.
    try:
        from apps.discord_bot.core.economy_rpc import guild_automation_effective
        from leagues import next_monday_0005_utc

        if await guild_automation_effective(db, guild_id):
            guild_config_update["next_auto_registration_at"] = next_monday_0005_utc(
                datetime.now(timezone.utc)
            ).isoformat()
    except Exception:
        logger.exception("Failed to schedule next auto registration after Force End guild=%s", guild_id)
    await db.table("guild_config").update(guild_config_update).eq("guild_id", guild_id).execute()

    n = len(ended_ids)
    extra = f" (+{n - 1} stuck season(s) cleared)" if n > 1 else ""

    if season["status"] == "registration":
        await interaction.followup.send(
            embed=success_embed(f"⏹️ Registration Season #{season['season_number']} cleared{extra}.")
        )
        await show_league_management(interaction, guild_id, owner_id)
        return

    standings = await fetch_standings(db, season["id"])
    winner = standings[0]["club_name"] if standings else "N/A"

    top_scorers = sorted(standings, key=lambda x: x["goals_for"], reverse=True)
    top_scorer_club = top_scorers[0]["club_name"] if top_scorers else "N/A"
    top_scorer_goals = top_scorers[0]["goals_for"] if top_scorers else 0

    best_defenses = sorted(standings, key=lambda x: x["goals_against"])
    best_defense_club = best_defenses[0]["club_name"] if best_defenses else "N/A"
    best_defense_goals = best_defenses[0]["goals_against"] if best_defenses else 0

    await interaction.followup.send(
        embed=success_embed(f"⏹️ **Season {season['season_number']} ended{extra}.** Standings finalized.")
    )

    summary_embed = discord.Embed(
        title=f"🏆 Season {season['season_number']} Summary & Awards",
        description=(
            f"The season has officially concluded! Here is the summary of achievements:\n\n"
            f"👑 **Champions**: **{winner}** 🏆\n"
            f"⚽ **Top Scoring Club**: **{top_scorer_club}** ({top_scorer_goals} goals)\n"
            f"🛡️ **Best Defense**: **{best_defense_club}** ({best_defense_goals} goals conceded)\n\n"
            f"**Final Standings:**\n"
        ),
        color=0xFFCC00
    )
    for idx, row in enumerate(standings[:5], 1):
        summary_embed.description += f"**{idx}. {row['club_name']}** — {row['points']} pts (GD: {row['goal_difference']})\n"

    thread = None
    if season.get("thread_format") == "dual_v2" and season.get("journal_thread_id"):
        thread = guild.get_thread(season["journal_thread_id"])
        if not thread:
            try:
                thread = await guild.fetch_channel(season["journal_thread_id"])
            except Exception:
                thread = None
    elif league_updates_thread_id:
        thread = guild.get_thread(league_updates_thread_id)
        if not thread:
            try:
                thread = await guild.fetch_channel(league_updates_thread_id)
            except Exception:
                thread = None

    if thread:
        try:
            await thread.send(embed=summary_embed)

            if season.get("thread_format") == "dual_v2":
                from apps.discord_bot.core.league_journal import archive_season_threads
                await archive_season_threads(guild, season, season_number=season["season_number"])
            else:
                from apps.discord_bot.core.thread_permissions import archive_thread_after_delay

                asyncio.create_task(
                    archive_thread_after_delay(thread, guild, delay=30.0)
                )
                try:
                    await thread.edit(name=f"🏆-season-{season['season_number']}-concluded")
                except Exception as err:
                    logger.warning(f"Failed to rename season thread {thread.id}: {err}")
        except Exception:
            logger.exception("Failed to send final summary to League Journal thread.")

    if chan_id:
        ann_embed = discord.Embed(
            title=f"🏁 ElevenBoss League: Season {season['season_number']} Concluded!",
            description=f"Congratulations to the champions **{winner}**! 🏆\n\n**Final Top 3:**\n",
            color=0xFFCC00
        )
        for idx, row in enumerate(standings[:3], 1):
            ann_embed.description += f"**{idx}. {row['club_name']}** — {row['points']} pts (GD: {row['goal_difference']})\n"
        from apps.discord_bot.cogs.league_cog import send_league_announcement
        await send_league_announcement(guild, chan_id, ann_embed, f"Season {season['season_number']} has concluded!")

    await show_league_management(interaction, guild_id, owner_id)


async def admin_kick_menu(interaction: discord.Interaction, guild_id: int, owner_id: int, admin_view: LeagueManagementView):
    db = await get_client()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        await interaction.followup.send(embed=error_embed("No league found for this server."), ephemeral=True)
        return
    season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        await interaction.followup.send(embed=error_embed("No active season found."), ephemeral=True)
        return

    standings = await fetch_standings(db, season["id"])

    embed = discord.Embed(
        title="🥾 Kick Inactive Manager",
        description="Select a human manager to kick. Kicking a manager turns their remaining fixtures into an AI Legacy club match.",
        color=0xFF3333
    )
    view = KickManagerSelectView(owner_id, admin_view, standings)
    await interaction.edit_original_response(embed=embed, view=view)


async def admin_execute_kick(interaction: discord.Interaction, kicked_id: int, guild_id: int, owner_id: int, admin_view: LeagueManagementView):
    db = await get_client()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        await interaction.followup.send(embed=error_embed("No league found for this server."), ephemeral=True)
        return
    season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        await interaction.followup.send(embed=error_embed("No active season found."), ephemeral=True)
        return

    await db.table("league_participants").update({"is_active": False}).eq("season_id", season["id"]).eq("player_id", kicked_id).execute()

    min_p_res = await db.table("players").select("discord_id").order("discord_id", desc=False).limit(1).execute()
    current_min = min_p_res.data[0]["discord_id"] if min_p_res.data else 0
    if current_min > 0:
        current_min = 0
    ai_id = current_min - 1

    user_p_res = await db.table("players").select("club_name").eq("discord_id", kicked_id).maybe_single().execute()
    old_club_name = user_p_res.data["club_name"] if user_p_res.data else "Kicked Club"
    ai_club_name = f"AI Legacy ({old_club_name})"

    ai_p = {
        "discord_id": ai_id,
        "username": ai_club_name,
        "club_name": ai_club_name,
        "manager_name": "AI Legacy Coach",
        "is_ai": True,
        "ai_rating": 65.0
    }
    await db.table("players").insert(ai_p).execute()

    await db.table("league_participants").insert({
        "season_id": season["id"],
        "player_id": ai_id
    }).execute()

    await db.table("league_fixtures").update({"home_team_id": ai_id}).eq("season_id", season["id"]).eq("home_team_id", kicked_id).eq("is_played", False).execute()
    await db.table("league_fixtures").update({"away_team_id": ai_id}).eq("season_id", season["id"]).eq("away_team_id", kicked_id).eq("is_played", False).execute()

    await db.rpc("scale_season_ai_opponents", {"p_season_id": season["id"]}).execute()

    await interaction.followup.send(embed=success_embed(f"🥾 **Manager kicked successfully.** Remaining unplayed fixtures swapped to **{ai_club_name}**."))
    await show_league_management(interaction, guild_id, owner_id)


async def admin_force_sim(interaction: discord.Interaction, guild_id: int, owner_id: int, admin_view: LeagueManagementView):
    db = await get_client()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        await interaction.followup.send(embed=error_embed("No league found for this server."), ephemeral=True)
        return
    season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        await interaction.followup.send(embed=error_embed("No active season found."), ephemeral=True)
        return

    curr = season["current_matchday"]

    fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season["id"]).eq("matchday", curr).eq("is_played", False).execute()
    fixtures = fixtures_res.data or []

    if not fixtures:
        await interaction.followup.send(embed=error_embed(f"No pending fixtures on Matchday {curr} to force-sim."), ephemeral=True)
        return

    for f in fixtures:
        await db.table("league_fixtures").update({"window_end": datetime.now(timezone.utc).isoformat()}).eq("id", f["id"]).execute()

    simulated = await auto_sim_expired_fixtures(db, season["id"], interaction.client)

    await interaction.followup.send(embed=success_embed(f"🎲 **Force-simulated {simulated} matches** for Matchday {curr}."))
    await show_league_management(interaction, guild_id, owner_id)


async def admin_duration_modal(interaction: discord.Interaction, admin_view: LeagueManagementView):
    modal = DurationModal(admin_view)
    await interaction.response.send_modal(modal)


async def admin_execute_set_duration(interaction: discord.Interaction, days: int, guild_id: int, owner_id: int, admin_view: LeagueManagementView):
    db = await get_client()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        await interaction.followup.send(embed=error_embed("No league found for this server."), ephemeral=True)
        return
    season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        await interaction.followup.send(embed=error_embed("No active season found."), ephemeral=True)
        return

    await db.table("league_seasons").update({"duration_days": days}).eq("id", season["id"]).execute()

    start_time = datetime.fromisoformat(season["start_time"].replace("Z", "+00:00"))
    total_weeks = season["total_matchdays"]
    window_duration = timedelta(days=days) / total_weeks

    fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season["id"]).eq("is_played", False).execute()
    fixtures = fixtures_res.data or []

    for f in fixtures:
        w_start = start_time + (f["matchday"] - 1) * window_duration
        w_end = start_time + f["matchday"] * window_duration
        await db.table("league_fixtures").update({
            "window_start": w_start.isoformat(),
            "window_end": w_end.isoformat()
        }).eq("id", f["id"]).execute()

    await interaction.followup.send(embed=success_embed(f"⏱️ **Season duration updated to {days} days.** Matchday windows recalculated."))
    await show_league_management(interaction, guild_id, owner_id)


# --- COG INTERFACE ---

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="admin", description="Private bot administrator settings (Bot Owner & DM only).")
    @app_commands.dm_only()
    @app_commands.check(is_owner)
    async def admin(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            await show_guild_select(interaction, interaction.user.id)
        except Exception as e:
            logger.exception("Failed to load Admin Control Panel.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))

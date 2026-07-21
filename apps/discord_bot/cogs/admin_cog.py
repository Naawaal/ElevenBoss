# apps/discord_bot/cogs/admin_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from leagues.league_time import (
    LeagueTimeError,
    coalesce_league_time,
    league_time_preview,
    parse_resolution_hour,
    validate_iana_timezone,
)

logger = logging.getLogger(__name__)



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




async def show_server_settings(interaction: discord.Interaction, guild_id: int, owner_id: int) -> None:
    """Server Settings — League Time only (027 autonomous admin policy)."""
    guild = interaction.client.get_guild(guild_id)
    if not guild:
        return

    db = await get_client()
    res = await db.table("guild_config").select(
        "league_timezone,league_resolution_hour_local"
    ).eq("guild_id", guild_id).maybe_single().execute()
    cfg = res.data or {}
    eff = coalesce_league_time(cfg.get("league_timezone"), cfg.get("league_resolution_hour_local"))
    preview = league_time_preview(
        eff.timezone, eff.resolution_hour_local, used_defaults=eff.used_defaults
    )

    embed = discord.Embed(
        title=f"⚙️ Server Settings — {guild.name}",
        description=(
            "League schedule preference for **future** seasons only.\n"
            "Active seasons keep their frozen timing snapshot."
        ),
        color=0x00FF87,
    )
    stored_tz = cfg.get("league_timezone") or "*(default)*"
    stored_hour = cfg.get("league_resolution_hour_local")
    hour_label = f"{stored_hour:02d}:00" if stored_hour is not None else "*(default)*"
    embed.add_field(name="Timezone", value=str(stored_tz), inline=True)
    embed.add_field(name="Daily resolution", value=hour_label, inline=True)
    embed.add_field(name="Preview", value=preview, inline=False)

    view = ServerSettingsView(owner_id, guild_id)
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

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⚙️ Server Settings", custom_id="admin_hub_server_settings", row=0)
    async def server_settings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_server_settings(interaction, self.guild_id, self.owner_id)

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



class ServerSettingsView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

    @discord.ui.button(
        style=discord.ButtonStyle.primary,
        label="🕐 League Time",
        custom_id="admin_server_league_time",
        row=0,
    )
    async def league_time_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = await get_client()
        res = await db.table("guild_config").select(
            "league_timezone,league_resolution_hour_local"
        ).eq("guild_id", self.guild_id).maybe_single().execute()
        cfg = res.data or {}
        await interaction.response.send_modal(LeagueTimeModal(self.guild_id, cfg))

    @discord.ui.button(
        style=discord.ButtonStyle.secondary,
        label="⬅️ Back to Admin Hub",
        custom_id="admin_server_settings_back",
        row=1,
    )
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_admin_hub(interaction, self.guild_id, self.owner_id)


class LeagueTimeModal(discord.ui.Modal, title="League Time"):
    timezone = discord.ui.TextInput(
        label="IANA timezone",
        placeholder="Asia/Kathmandu",
        default="UTC",
        max_length=64,
    )
    hour = discord.ui.TextInput(
        label="Daily resolution time (local HH or HH:MM)",
        placeholder="20:00",
        default="0",
        max_length=5,
    )

    def __init__(self, guild_id: int, cfg: dict | None = None) -> None:
        super().__init__()
        self.guild_id = guild_id
        cfg = cfg or {}
        if cfg.get("league_timezone"):
            self.timezone.default = str(cfg["league_timezone"])
        if cfg.get("league_resolution_hour_local") is not None:
            self.hour.default = str(int(cfg["league_resolution_hour_local"]))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            tz_name = validate_iana_timezone(self.timezone.value)
            hour_val = parse_resolution_hour(self.hour.value)
        except LeagueTimeError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        # Upsert preference only — never touch season/matchday freeze columns.
        db = await get_client()
        await db.table("guild_config").upsert({
            "guild_id": self.guild_id,
            "league_timezone": tz_name,
            "league_resolution_hour_local": hour_val,
        }, on_conflict="guild_id").execute()

        preview = league_time_preview(tz_name, hour_val, used_defaults=False)
        await interaction.followup.send(
            embed=success_embed(f"Saved League Time.\n\n{preview}"),
            ephemeral=True,
        )
        try:
            await show_server_settings(interaction, self.guild_id, interaction.user.id)
        except Exception:
            pass



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

# apps/discord_bot/cogs/admin_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

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
    embed.add_field(name="📢 Announcements Channel", value=channel_str, inline=True)
    embed.add_field(name="🎖️ Announcements Role", value=role_str, inline=True)
    embed.add_field(name="🏆 League Status", value=config.get("league_status", "inactive").upper(), inline=False)

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
        description="Configure target channels and roles for automated league announcements.",
        color=0x00FF87
    )
    embed.add_field(name="Target Channel", value=channel_str, inline=True)
    embed.add_field(name="Target Role", value=role_str, inline=True)

    view = AnnouncementSubView(owner_id, guild_id)
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

    @discord.ui.button(style=discord.ButtonStyle.primary, label="📢 Announcements", custom_id="admin_hub_announce")
    async def announce_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🏆 League Management (Soon)", custom_id="admin_hub_league", disabled=True)
    async def league_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🔄 Switch Server", custom_id="admin_hub_switch")
    async def switch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_guild_select(interaction, self.owner_id)

class AnnouncementSubView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

    @discord.ui.button(style=discord.ButtonStyle.primary, label="Set Channel", custom_id="announce_set_channel")
    async def channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = ChannelSelectView(self.owner_id, self.guild_id, guild)
        embed = discord.Embed(title="📢 Configure Channel", description="Choose the text channel for announcements:", color=0x00FF87)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    @discord.ui.button(style=discord.ButtonStyle.primary, label="Set Role", custom_id="announce_set_role")
    async def role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.client.get_guild(self.guild_id)
        view = RoleSelectView(self.owner_id, self.guild_id, guild)
        embed = discord.Embed(title="📢 Configure Role", description="Choose the target role for announcement mentions:", color=0x00FF87)
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Admin Hub", custom_id="announce_back_hub")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_admin_hub(interaction, self.guild_id, self.owner_id)

class ChannelSelectView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int, guild: discord.Guild | None) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

        options = []
        if guild:
            # Filter first 25 text channels where the bot has permission
            for channel in guild.text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.view_channel and permissions.send_messages:
                    options.append(
                        discord.SelectOption(
                            label=f"#{channel.name}",
                            value=str(channel.id),
                            description=f"ID: {channel.id}"
                        )
                    )
                if len(options) >= 25:
                    break

        if not options:
            options.append(
                discord.SelectOption(
                    label="No eligible channels found",
                    value="none",
                    description="Make sure the bot has permissions in text channels."
                )
            )

        select = discord.ui.Select(placeholder="Select Announcement Channel...", options=options)
        select.callback = self.channel_select_callback
        self.add_item(select)

        cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Cancel")
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

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

        # Update Supabase
        db = await get_client()
        await db.table("guild_config").update({"league_channel_id": channel_id}).eq("guild_id", self.guild_id).execute()

        await interaction.followup.send(f"✅ Announcement channel updated to {channel.mention}.", ephemeral=True)
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)

class RoleSelectView(BaseAdminView):
    def __init__(self, owner_id: int, guild_id: int, guild: discord.Guild | None) -> None:
        super().__init__(owner_id)
        self.guild_id = guild_id

        options = []
        if guild:
            # Filter first 25 non-default roles
            roles = [r for r in guild.roles if not r.is_default()]
            for role in roles[:25]:
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
                    label="No roles found",
                    value="none",
                    description="Create a role in the server first."
                )
            )

        select = discord.ui.Select(placeholder="Select Announcement Role...", options=options)
        select.callback = self.role_select_callback
        self.add_item(select)

        cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="⬅️ Cancel")
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

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

        # Update Supabase
        db = await get_client()
        await db.table("guild_config").update({"announcement_role_id": role_id}).eq("guild_id", self.guild_id).execute()

        await interaction.followup.send(f"✅ Announcement role updated to **{role.name}**.", ephemeral=True)
        await show_announcements_menu(interaction, self.guild_id, self.owner_id)


# --- COG INTERFACE ---

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="admin", description="Private bot administrator settings (Bot Owner & DM only).")
    @app_commands.dm_only()
    @app_commands.check(is_owner)
    async def admin(self, interaction: discord.Interaction) -> None:
        # Check if deferred
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            await show_guild_select(interaction, interaction.user.id)
        except Exception as e:
            logger.exception("Failed to load Admin Control Panel.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))

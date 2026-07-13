# apps/discord_bot/cogs/profile_cog.py
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from leagues import tier_progress_label

from apps.discord_bot.core.competitive_display import profile_leaderboard_hint
from apps.discord_bot.core.economy_rpc import format_action_energy_status_async, sync_action_energy
from apps.discord_bot.core.view_helpers import disable_view_on_timeout, edit_ephemeral_hub_message
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.embeds.profile_embeds import format_finance_section, format_hospital_summary
from apps.discord_bot.middleware.guard import ensure_registered

logger = logging.getLogger(__name__)


async def _publish_profile(
    interaction: discord.Interaction,
    embed: discord.Embed,
    view: discord.ui.View,
) -> None:
    """Publish/refresh profile hub; clear attachments (e.g. squad pitch) when returning."""
    if not interaction.response.is_done():
        await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        return
    if interaction.message is not None:
        try:
            await interaction.followup.edit_message(
                interaction.message.id, embed=embed, view=view, attachments=[]
            )
            return
        except discord.NotFound:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return
    try:
        await interaction.edit_original_response(embed=embed, view=view, attachments=[])
    except discord.HTTPException:
        await edit_ephemeral_hub_message(interaction, embed, view)


async def show_profile(interaction: discord.Interaction, owner_id: int) -> None:
    """Single refresh entry for `/profile` and Back-to-Profile paths."""
    db = await get_client()
    result = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = result.data if result else None
    if not player:
        await interaction.followup.send(
            embed=error_embed("Profile not found despite registration check."),
            ephemeral=True,
        )
        return

    energy_row = await sync_action_energy(db, owner_id)
    curr_energy = energy_row.get("action_energy", player.get("action_energy", player.get("energy", 0)))
    max_energy = energy_row.get("max_energy", player.get("max_energy", 120))
    energy_status = await format_action_energy_status_async(db, curr_energy, max_energy)
    gems = int(player.get("tokens", 0))

    hospital_unavailable = False
    patients: list[dict] = []
    try:
        patients_res = await db.table("hospital_patients").select(
            "*, player_cards(id, name, position, injury_tier)"
        ).eq("owner_id", owner_id).is_("discharge_date", "null").execute()
        patients = patients_res.data or []
    except Exception:
        logger.exception("Failed to load hospital patients for profile owner_id=%s", owner_id)
        hospital_unavailable = True

    div_res = await db.table("global_divisions").select("*").order("min_lp").execute()
    divisions = div_res.data or []
    user_lp = player.get("global_lp", 0)

    current_div = None
    next_div = None
    for idx, div in enumerate(divisions):
        if user_lp >= div["min_lp"]:
            current_div = div
            next_div = divisions[idx + 1] if idx + 1 < len(divisions) else None

    if not current_div:
        current_div = {"name": "Bronze III", "min_lp": 0}
        if len(divisions) > 1:
            next_div = divisions[1]

    bar_len = 10
    if not next_div:
        progress_bar = f"`[{'█' * bar_len}]` **{user_lp} LP** (Max Division)"
    else:
        min_lp = current_div["min_lp"]
        max_lp = next_div["min_lp"]
        range_lp = max_lp - min_lp
        progress_lp = user_lp - min_lp
        ratio = max(0.0, min(1.0, progress_lp / range_lp)) if range_lp > 0 else 0.0
        filled = int(ratio * bar_len)
        empty = bar_len - filled
        bar_str = f"[{'█' * filled}{'░' * empty}]"
        progress_bar = f"`{bar_str}` **{user_lp}/{max_lp} LP** to {next_div['name']}"

    # guild_only: DMs blocked by Discord; no custom DM dashboard in v1 (FR-010).
    embed = discord.Embed(
        title=f"🛡️ Club Profile: {player['club_name']}",
        color=0x00FF87,
    )
    embed.add_field(name="👔 Manager Name", value=player["manager_name"], inline=True)
    user = interaction.user
    embed.add_field(name="👤 Username", value=user.name, inline=True)
    embed.add_field(
        name="💰 Club Finance",
        value=format_finance_section(int(player.get("coins", 0)), gems),
        inline=False,
    )
    embed.add_field(
        name="🏥 Hospital",
        value=format_hospital_summary(
            int(player.get("hospital_level", 0)),
            patients,
            unavailable=hospital_unavailable,
            intensity_tier=int(player.get("intensity_tier") or 0) or None,
            division=player.get("division"),
        ),
        inline=False,
    )
    embed.add_field(name="⚡ Action Energy", value=energy_status, inline=False)
    embed.add_field(name="🌍 Global Division", value=current_div["name"], inline=True)
    embed.add_field(name="🏆 Global LP Progress", value=progress_bar, inline=False)
    embed.add_field(name="⚔️ Server Division", value=player["division"], inline=True)
    embed.add_field(
        name="📊 Division Rank Points",
        value=f"{player['league_points']} pts (GD: {player['goal_difference']})",
        inline=True,
    )
    embed.add_field(
        name="📈 Weekly tiers",
        value=tier_progress_label(int(player.get("league_points", 0))),
        inline=True,
    )
    best_pts = player.get("best_weekly_pts") or 0
    if best_pts:
        embed.add_field(name="🏅 Best weekly", value=f"**{best_pts}** pts", inline=True)
    embed.add_field(
        name="ℹ️ Rankings",
        value=(
            "**Division Rank** = bot battles (weekly). **Season Pts** = `/league hub`. "
            "Use **`/leaderboard`** for full tables."
        ),
        inline=False,
    )

    w, d, l = player["wins"], player["draws"], player["losses"]
    record = f"{w}W - {d}D - {l}L"
    embed.add_field(
        name="⚽ Match Record",
        value=f"{record} ({player['matches_played']} played)",
        inline=True,
    )

    hist_res = await db.table("player_league_history").select("*").eq(
        "player_id", owner_id
    ).order("created_at", desc=True).limit(5).execute()
    history = hist_res.data or []
    if history:
        trophy_lines = []
        for h in history:
            awards = h.get("awards_json") or []
            award_label = awards[0].get("type", "participant") if awards else "participant"
            trophy_lines.append(
                f"Season #{h.get('season_id', '')[:8]}… — **#{h['finish_position']}** ({award_label})"
            )
        embed.add_field(name="🏆 Trophy Cabinet", value="\n".join(trophy_lines), inline=False)

    embed.set_footer(
        text=(
            f"{profile_leaderboard_hint()} · /store for daily bonus · "
            "Hub buttons below · re-run /profile if buttons expire"
        )
    )

    view = ProfileHubView(owner_id)
    await _publish_profile(interaction, embed, view)


class ProfileHubView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🏥 Manage Hospital", row=0)
    async def manage_hospital(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.views.store_facilities import show_hospital_panel
        await show_hospital_panel(interaction, self.owner_id, origin="profile")

    @discord.ui.button(style=discord.ButtonStyle.success, label="🌱 Manage Academy", row=0)
    async def manage_academy(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.views.academy_hub import show_academy_hub
        await show_academy_hub(interaction, self.owner_id, origin="profile")

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="💰 Finances", row=1)
    async def finances(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.cogs.economy_cog import show_club_finances_panel
        await show_club_finances_panel(interaction, self.owner_id)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="📊 View Club Stats", row=1)
    async def club_stats(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.cogs.squad_cog import show_squad_hub
        await show_squad_hub(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="View your club's profile, academy, hospital, finances, and record.",
    )
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def profile(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            await show_profile(interaction, interaction.user.id)
        except Exception as e:
            logger.exception("Failed to fetch profile.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while loading your profile: {str(e)}"),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))

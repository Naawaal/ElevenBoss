# apps/discord_bot/cogs/economy_cog.py
from __future__ import annotations

import discord
from discord.ext import commands

from economy import GameConfig, calculate_weekly_wages
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.core.view_helpers import disable_view_on_timeout, edit_ephemeral_hub_message


def build_club_finances_embed(
    player: dict,
    starting_cards: list[dict],
    weekly_wages: int,
    *,
    profile_pointer: bool = False,
) -> discord.Embed:
    tokens = int(player.get("tokens", 0))
    embed = discord.Embed(
        title=f"💼 Club Finances: {player['club_name']}",
        description=f"Financial statement and forecasts for Manager **{player['manager_name']}**.",
        color=0x00FF87,
    )
    embed.add_field(
        name="💰 Wallet Balances",
        value=(
            f"🪙 **Coins Balance**: `{player['coins']:,} coins`\n"
            f"💎 **Gems Balance**: `{tokens:,} gems`"
        ),
        inline=False,
    )
    embed.add_field(
        name="👔 Starting 11 Wage Bill (forecast)",
        value=(
            f"👥 **Active Starting Players**: `{len(starting_cards)}/11`\n"
            f"📉 **Estimated weekly wages**: `🪙 {weekly_wages:,} coins / week` *(not auto-deducted)*"
        ),
        inline=False,
    )
    embed.add_field(
        name="🏗️ Club Facilities",
        value=(
            f"🌱 Youth Academy **L{player.get('youth_academy_level', 1)}** · "
            f"🏋️ Training Ground **L{player.get('training_ground_level', 1)}** · "
            f"🏥 Hospital **L{player.get('hospital_level', 0)}**"
        ),
        inline=False,
    )
    if profile_pointer:
        embed.set_footer(text="Unified club dashboard (finance + hospital): /profile")
    return embed


async def fetch_club_finances_embed(owner_id: int, *, profile_pointer: bool = False) -> discord.Embed | None:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data if player_res else None
    if not player:
        return None
    assignments_res = await db.table("squad_assignments").select("player_cards(*)").eq("discord_id", owner_id).execute()
    starting_cards = [a["player_cards"] for a in (assignments_res.data or []) if a.get("player_cards")]
    weekly_wages = calculate_weekly_wages(starting_cards, GameConfig())
    return build_club_finances_embed(
        player, starting_cards, weekly_wages, profile_pointer=profile_pointer
    )


class ClubFinancesPanelView(discord.ui.View):
    """Finances detail opened from /profile; Back refreshes the profile dashboard."""

    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Profile", row=0)
    async def back(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.cogs.profile_cog import show_profile
        await show_profile(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


async def show_club_finances_panel(interaction: discord.Interaction, owner_id: int) -> None:
    embed = await fetch_club_finances_embed(owner_id, profile_pointer=False)
    if embed is None:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return
    view = ClubFinancesPanelView(owner_id)
    await edit_ephemeral_hub_message(interaction, embed, view)


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))

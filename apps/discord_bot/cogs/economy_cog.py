# apps/discord_bot/cogs/economy_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from economy import GameConfig, calculate_weekly_wages, generate_agent_offer
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="club-finances", description="View club balance ledger, wage sheets, and finance forecasts.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def club_finances(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player/club metadata
            player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None
            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            # 2. Fetch starting 11 cards
            assignments_res = await db.table("squad_assignments").select("player_cards(*)").eq("discord_id", interaction.user.id).execute()
            starting_cards = [a["player_cards"] for a in assignments_res.data if a.get("player_cards")]

            # 3. Calculate weekly wages
            config = GameConfig()
            weekly_wages = calculate_weekly_wages(starting_cards, config)

            # Get tokens safely (default to 0 if not present)
            tokens = player.get("tokens", 0)

            # 4. Render embed
            embed = discord.Embed(
                title=f"💼 Club Finances: {player['club_name']}",
                description=f"Financial statement and forecasts for Manager **{player['manager_name']}**.",
                color=0x00FF87
            )
            embed.add_field(
                name="💰 Wallet Balances",
                value=(
                    f"🪙 **Coins Balance**: `{player['coins']:,} coins`\n"
                    f"💎 **Gems Balance**: `{tokens:,} gems`"
                ),
                inline=False
            )
            embed.add_field(
                name="👔 Starting 11 Wage Bill (forecast)",
                value=(
                    f"👥 **Active Starting Players**: `{len(starting_cards)}/11`\n"
                    f"📉 **Estimated weekly wages**: `🪙 {weekly_wages:,} coins / week` *(not auto-deducted)*"
                ),
                inline=False
            )

            embed.add_field(
                name="📈 Balance",
                value=f"Current coins: `🪙 {player['coins']:,}`",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to fetch club finances.")
            await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))

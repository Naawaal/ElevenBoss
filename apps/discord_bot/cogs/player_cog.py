# apps/discord_bot/cogs/player_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands

from economy import level_up_cost, rarity_rating_cap, compute_new_overall
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

logger = logging.getLogger(__name__)

class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="player-level-up", description="Spend coins to level up a player and increase their overall rating.")
    @app_commands.check(ensure_registered)
    async def player_level_up(self, interaction: discord.Interaction, player_id: str) -> None:
        # Prevent Discord API 3-second timeout
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()

            # 1. Fetch player card details
            card_res = await db.table("player_cards").select("*").eq("id", player_id).maybe_single().execute()
            card = card_res.data if card_res else None

            if not card:
                await interaction.followup.send(embed=error_embed("Player card not found."), ephemeral=True)
                return

            if card["owner_id"] != interaction.user.id:
                await interaction.followup.send(embed=error_embed("You do not own this player card."), ephemeral=True)
                return

            # 2. Check current rating caps
            rarity = card["rarity"]
            current_overall = card["overall"]
            cap = rarity_rating_cap(rarity)

            if current_overall >= cap:
                await interaction.followup.send(
                    embed=error_embed(
                        f"**{card['name']}** has already reached the rating cap of **{cap} OVR** for **{rarity}** rarity."
                    ),
                    ephemeral=True
                )
                return

            # 3. Calculate level up cost and validation
            curr_level = card["level"]
            cost = level_up_cost(curr_level)

            # Fetch player account coins
            player_res = await db.table("players").select("coins").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None
            
            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            if player["coins"] < cost:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Insufficient coins. Level up costs **{cost} coins**, but you only have **{player['coins']}**."
                    ),
                    ephemeral=True
                )
                return

            # 4. Perform computations
            new_level = curr_level + 1
            new_overall = compute_new_overall(new_level, card["base_rating"], rarity)
            new_coins = player["coins"] - cost

            # 5. Database Writes: update player coins and update card level/overall
            await db.table("players").update({"coins": new_coins}).eq("discord_id", interaction.user.id).execute()
            await db.table("player_cards").update({
                "level": new_level,
                "overall": new_overall
            }).eq("id", player_id).execute()

            # 6. Respond with success embed
            embed = success_embed(
                f"🎉 **{card['name']}** has levelled up to **Level {new_level}**!\n\n"
                f"**Rating**: {current_overall} ➔ **{new_overall} OVR**\n"
                f"**Coins Spent**: {cost} coins\n"
                f"**Remaining Balance**: {new_coins} coins"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to level up player.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while levelling up: {str(e)}"),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlayerCog(bot))

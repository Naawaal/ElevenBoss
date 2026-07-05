# apps/discord_bot/cogs/match_cog.py
from __future__ import annotations
import logging
import random
import discord
from discord import app_commands
from discord.ext import commands

from match_engine import MatchPlayerCard, MatchInput, simulate_match
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.match_embeds import match_result_embed
from apps.discord_bot.embeds.common_embeds import error_embed

logger = logging.getLogger(__name__)

DIVISION_OPPONENT_RATINGS = {
    "Grassroots": 55.0,
    "Amateur": 65.0,
    "Semi-Pro": 75.0,
    "Professional": 82.0,
    "Elite": 88.0,
    "Legendary": 94.0,
}

OPPONENT_NAMES = {
    "Grassroots": ["Local Pub FC", "Sunday League United", "Park Wanderers"],
    "Amateur": ["Metro Athletic", "Town Rovers", "Suburban City"],
    "Semi-Pro": ["County Rangers", "District FC", "State Alliance"],
    "Professional": ["Apex Rovers", "Vanguard City", "Dynamo FC"],
    "Elite": ["Zenith United", "Sovereign Athletic", "Majestic FC"],
    "Legendary": ["Titan Legends", "Antigravity FC", "Grandmasters United"],
}

class MatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="match-play", description="Simulate a league match against a division-calibrated AI opponent (costs 10 energy).")
    @app_commands.check(ensure_registered)
    async def match_play(self, interaction: discord.Interaction) -> None:
        # Prevent Discord API 3-second timeout
        await interaction.response.defer(ephemeral=False)
        try:
            db = await get_client()

            # 1. Fetch player metadata
            player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = player_res.data if player_res else None
            
            if not player:
                await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
                return

            # 2. Check energy requirement
            if player["energy"] < 10:
                await interaction.followup.send(
                    embed=error_embed(f"Insufficient energy. Matches require **10 energy**, but you only have **{player['energy']}**."),
                    ephemeral=True
                )
                return

            # 3. Fetch starting 11 via junction table
            assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", interaction.user.id).execute()
            assignments = assignments_res.data or []

            # Filter out assignments with missing card data
            active_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
            count = len(active_cards)

            if count != 11:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Your starting squad must have exactly **11 players** assigned to play a match (current: **{count}/11**).\n"
                        "Configure your starting 11 using `/squad-view` first."
                    ),
                    ephemeral=True
                )
                return

            # 4. Run match simulation
            match_cards = [
                MatchPlayerCard(
                    name=c["name"],
                    position=c["position"],
                    overall=c["overall"]
                )
                for c in active_cards
            ]

            division = player["division"]
            opp_rating = DIVISION_OPPONENT_RATINGS.get(division, 55.0)
            opp_name = random.choice(OPPONENT_NAMES.get(division, ["AI Club"]))

            match_input = MatchInput(my_players=match_cards, opponent_base_rating=opp_rating)
            result = simulate_match(match_input)

            # 5. Calculate new user stats
            new_energy = player["energy"] - 10
            new_coins = player["coins"] + result.coins_earned
            new_points = player["league_points"] + result.points_earned
            new_gd = player["goal_difference"] + (result.goals_for - result.goals_against)
            new_matches_played = player["matches_played"] + 1

            new_wins = player["wins"] + (1 if result.result == "win" else 0)
            new_draws = player["draws"] + (1 if result.result == "draw" else 0)
            new_losses = player["losses"] + (1 if result.result == "loss" else 0)

            # 6. Database Writes: update player row and insert history (run sequentially)
            await db.table("players").update({
                "energy": new_energy,
                "coins": new_coins,
                "league_points": new_points,
                "goal_difference": new_gd,
                "matches_played": new_matches_played,
                "wins": new_wins,
                "draws": new_draws,
                "losses": new_losses
            }).eq("discord_id", interaction.user.id).execute()

            await db.table("match_history").insert({
                "player_id": interaction.user.id,
                "result": result.result,
                "my_rating": result.my_rating,
                "opponent_rating": result.opponent_rating,
                "goals_for": result.goals_for,
                "goals_against": result.goals_against,
                "coins_earned": result.coins_earned,
                "points_earned": result.points_earned
            }).execute()

            # 7. Respond with match result embed
            embed = match_result_embed(result, player["club_name"], opp_name)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Failed to simulate match.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while simulating the match: {str(e)}")
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchCog(bot))

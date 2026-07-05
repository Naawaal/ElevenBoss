# apps/discord_bot/cogs/match_cog.py
from __future__ import annotations
import logging
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from match_engine import MatchPlayerCard, MatchInput, simulate_match, EventType, generate_match_script
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
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

            # 5. Generate commentary script
            events = generate_match_script(result, player["club_name"], opp_name)

            # 6. Post Match Ticket in the main channel
            ticket_embed = discord.Embed(
                title=f"🎫 Match Ticket: {player['club_name']} vs {opp_name}",
                description="A new league match has kicked off! Live commentary is streaming now.",
                color=0x00FF87
            )
            ticket_embed.add_field(name="Division", value=player["division"], inline=True)
            ticket_embed.add_field(name="Cost", value="⚡ 10 Energy", inline=True)
            ticket_msg = await interaction.followup.send(embed=ticket_embed)

            # 7. Spawn the Live Stadium public thread on the ticket message
            thread = None
            if interaction.guild and hasattr(interaction.channel, "create_thread"):
                try:
                    thread = await interaction.channel.create_thread(
                        name=f"🏟️ {player['club_name']} vs {opp_name} - Live",
                        message=ticket_msg,
                        auto_archive_duration=60
                    )
                except Exception as e:
                    logger.warning(f"Failed to create public match thread: {e}. Falling back to main channel.")

            # Update ticket embed if thread was successfully created
            if thread:
                ticket_embed.add_field(name="Stadium Thread", value=thread.mention, inline=False)
                await ticket_msg.edit(embed=ticket_embed)

            # 8. Setup target message for commentary stream
            target = thread if thread else interaction.channel

            init_embed = discord.Embed(
                title=f"⚽ Live: {player['club_name']} vs {opp_name}",
                color=0x00FF87
            )
            init_embed.add_field(name="Scoreboard", value=f"🏟️ **{player['club_name']}** `0 - 0` **{opp_name}**", inline=False)
            init_embed.add_field(name="Commentary Ticker", value="🟢 **0'** - Kickoff! The match is underway.", inline=False)
            
            ticker_msg = await target.send(embed=init_embed)

            # 9. Commentary Live Loop
            ticker_history: list[str] = []
            for ev in events:
                emoji_map = {
                    EventType.KICKOFF: "🟢",
                    EventType.GOAL: "⚽",
                    EventType.MISS: "❌",
                    EventType.SAVE: "🧤",
                    EventType.YELLOW_CARD: "🟨",
                    EventType.FULL_TIME: "🏁"
                }
                emo = emoji_map.get(ev.type, "⏱️")
                
                ticker_history.append(f"{emo} **{ev.minute}'** - {ev.text}")
                recent_ticker = ticker_history[-5:] # Show only the last 5 events
                
                score_str = ev.score_update or "0 - 0"
                
                embed = discord.Embed(
                    title=f"⚽ Live: {player['club_name']} vs {opp_name}",
                    color=0x00FF87
                )
                embed.add_field(name="Scoreboard", value=f"🏟️ **{player['club_name']}** `{score_str}` **{opp_name}**", inline=False)
                embed.add_field(name="Commentary Ticker", value="\n".join(recent_ticker), inline=False)
                
                await ticker_msg.edit(embed=embed)
                
                # Dynamic sleep
                sleep_time = 2.0 if ev.type == EventType.FULL_TIME else 1.5
                await asyncio.sleep(sleep_time)

            # 10. Calculate user rewards and ratings
            new_energy = player["energy"] - 10
            new_coins = player["coins"] + result.coins_earned
            new_points = player["league_points"] + result.points_earned
            new_gd = player["goal_difference"] + (result.goals_for - result.goals_against)
            new_matches_played = player["matches_played"] + 1

            new_wins = player["wins"] + (1 if result.result == "win" else 0)
            new_draws = player["draws"] + (1 if result.result == "draw" else 0)
            new_losses = player["losses"] + (1 if result.result == "loss" else 0)

            # 11. Database Writes (only after ticker completes successfully)
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

            # 12. Send Post-Match Press Conference UI (distinct gold color scheme)
            press_embed = discord.Embed(
                title="🎙️ Post-Match Press Conference",
                description="Reporters gather as the managers discuss the game statistics and performance.",
                color=0xFFCC00  # Visually distinct Gold color
            )
            
            result_emoji = "🎉 WIN" if result.result == "win" else ("🤝 DRAW" if result.result == "draw" else "💔 LOSS")
            
            press_embed.add_field(
                name="🥅 Final Result",
                value=f"### {result_emoji}\n**{player['club_name']}** `{result.goals_for} - {result.goals_against}` **{opp_name}**",
                inline=False
            )
            
            press_embed.add_field(
                name="📊 Match Statistics",
                value=(
                    f"**Possession**: {result.possession_home}% - {result.possession_away}%\n"
                    f"**Shots**: {result.shots_home} - {result.shots_away}\n"
                    f"**Man of the Match**: ⭐ **{result.motm}**"
                ),
                inline=True
            )
            
            press_embed.add_field(
                name="🎁 Rewards & Standings",
                value=(
                    f"🪙 **+{result.coins_earned} coins**\n"
                    f"🏆 **+{result.points_earned} league pts**"
                ),
                inline=True
            )
            
            press_embed.set_footer(text="✅ Rewards and match history saved to database.")
            await target.send(embed=press_embed)

            # 13. Thread cleanup (rename and schedule archive)
            if thread:
                try:
                    await thread.edit(name=f"🏆 {player['club_name']} {result.goals_for}-{result.goals_against} {opp_name}")
                except Exception as e:
                    logger.warning(f"Failed to rename thread: {e}")

                async def archive_thread_after_delay(t: discord.Thread, delay: float) -> None:
                    await asyncio.sleep(delay)
                    try:
                        await t.edit(locked=True, archived=True)
                    except discord.NotFound:
                        logger.info(f"Thread {t.id} was already deleted or not found.")
                    except Exception as err:
                        logger.warning(f"Failed to lock and archive thread {t.id}: {err}")

                asyncio.create_task(archive_thread_after_delay(thread, 180.0))

        except Exception as e:
            logger.exception("Failed to simulate match.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while simulating the match: {str(e)}")
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchCog(bot))

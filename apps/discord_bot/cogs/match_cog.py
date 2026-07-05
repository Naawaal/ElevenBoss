# apps/discord_bot/cogs/match_cog.py
from __future__ import annotations
import logging
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from match_engine import (
    MatchPlayerCard,
    MatchInput,
    simulate_match,
    EventType,
    generate_match_script,
    CommentaryEngine,
    MatchState,
    stream_match,
    MatchResult
)
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

def get_momentum_bar(momentum: int) -> str:
    """Builds a beautiful visual momentum bar indicator."""
    bars = 10
    pos = int((momentum + 100) / 200 * bars)
    pos = max(0, min(bars, pos))
    bar = ["░"] * (bars + 1)
    bar[pos] = "🔵"
    return f"`[{''.join(bar)}]` ({momentum:+})"

class TouchlineView(discord.ui.View):
    def __init__(self, state: MatchState, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.state = state
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This dashboard is only for the active manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.danger, label="⚔️ Attack", custom_id="touchline_attack")
    async def attack_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 1.3
        await interaction.response.send_message("📣 **Touchline**: Tactical focus shifted to **Attack**!", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⚖️ Balanced", custom_id="touchline_balanced")
    async def balanced_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 1.0
        await interaction.response.send_message("📣 **Touchline**: Tactics set to **Balanced** shape.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🛡️ Defend", custom_id="touchline_defend")
    async def defend_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 0.7
        await interaction.response.send_message("📣 **Touchline**: Tactical focus shifted to **Defend**!", ephemeral=True)

class MatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="match-play", description="Simulate a league match with dynamic interactive touchline updates.")
    @app_commands.check(ensure_registered)
    async def match_play(self, interaction: discord.Interaction) -> None:
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

            # 3. Fetch starting 11 details
            assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", interaction.user.id).execute()
            assignments = assignments_res.data or []
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

            # 4. Construct MatchPlayerCard models including core attributes and morale
            match_cards = []
            for c in active_cards:
                # Resolve playstyles
                ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", c["id"]).execute()
                playstyles = [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []

                match_cards.append(
                    MatchPlayerCard(
                        name=c["name"],
                        position=c["position"],
                        overall=c["overall"],
                        pac=c.get("pac", 50),
                        sho=c.get("sho", 50),
                        pas=c.get("pas", 50),
                        dri=c.get("dri", 50),
                        def_stat=c.get("def", 50), # resolves alias
                        phy=c.get("phy", 50),
                        morale=c.get("morale", 80),
                        playstyles=playstyles
                    )
                )

            division = player["division"]
            opp_rating = DIVISION_OPPONENT_RATINGS.get(division, 55.0)
            opp_name = random.choice(OPPONENT_NAMES.get(division, ["AI Club"]))

            # Compute manager team base rating
            my_rating = sum(p.overall for p in match_cards) / len(match_cards)

            # 5. Instantiate V2 MatchState and CommentaryEngine
            state = MatchState(home_rating=my_rating, away_rating=opp_rating)
            commentary_engine = CommentaryEngine()

            # 6. Post Match Ticket in parent channel
            ticket_embed = discord.Embed(
                title=f"🎫 Match Ticket: {player['club_name']} vs {opp_name}",
                description="A new league match has kicked off! Live commentary is streaming now.",
                color=0x00FF87
            )
            ticket_embed.add_field(name="Division", value=player["division"], inline=True)
            ticket_embed.add_field(name="Cost", value="⚡ 10 Energy", inline=True)
            ticket_msg = await interaction.followup.send(embed=ticket_embed)

            # 7. Spawn Live Stadium public thread
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

            if thread:
                ticket_embed.add_field(name="Stadium Thread", value=thread.mention, inline=False)
                await ticket_msg.edit(embed=ticket_embed)

            target = thread if thread else interaction.channel

            # 8. Send Initial Live Match Embed containing Touchline Interactivity View
            init_embed = discord.Embed(
                title=f"🏟️ Live Stadium: {player['club_name']} vs {opp_name}",
                color=0x00FF87
            )
            init_embed.add_field(name="Scoreboard", value=f"🏟️ **{player['club_name']}** `0 - 0` **{opp_name}**", inline=False)
            init_embed.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
            init_embed.add_field(name="Commentary Ticker", value="🟢 **0'** - The referee blows the whistle and we are underway!", inline=False)

            touchline_view = TouchlineView(state, interaction.user.id)
            ticker_msg = await target.send(embed=init_embed, view=touchline_view)

            # Construct mock opponent squad for simulator selection
            opp_squad = [
                MatchPlayerCard(name="Opponent Striker", position="FWD", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Midfielder", position="MID", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Defender", position="DEF", overall=int(opp_rating)),
            ]

            # 9. Commentary Live Loop Generator Streaming
            ticker_history: list[str] = []
            
            async for ev in stream_match(state, match_cards, opp_squad, player["club_name"], opp_name):
                # Retrieve contextual commentary
                variables = {
                    "actor": ev["actor"],
                    "team": ev["team"]
                }
                comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
                text = comm["text"]
                urgency = comm["urgency"]

                emoji_map = {
                    "KICKOFF": "🟢",
                    "GOAL": "⚽",
                    "MISS": "❌",
                    "CHANCE": "🎯",
                    "FOUL": "🟨",
                    "FULL_TIME": "🏁"
                }
                emo = emoji_map.get(ev["type"], "⏱️")

                ticker_history.append(f"{emo} **{ev['minute']}'** - {text}")
                recent_ticker = ticker_history[-5:]

                # Update live embed
                embed = discord.Embed(
                    title=f"🏟️ Live Stadium: {player['club_name']} vs {opp_name}",
                    color=0x00FF87
                )
                embed.add_field(name="Scoreboard", value=f"🏟️ **{player['club_name']}** `{ev['score_update']}` **{opp_name}**", inline=False)
                embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
                embed.add_field(name="Commentary Ticker", value="\n".join(recent_ticker), inline=False)

                await ticker_msg.edit(embed=embed, view=touchline_view)

                # Dynamic sleep pacing based on commentary urgency
                if ev["type"] == "FULL_TIME":
                    sleep_time = 2.0
                elif urgency == "cliffhanger":
                    sleep_time = 3.5
                elif urgency == "build_up":
                    sleep_time = 2.5
                else:
                    sleep_time = 1.5

                await asyncio.sleep(sleep_time)

            # Disable touchline view options
            for child in touchline_view.children:
                child.disabled = True
            await ticker_msg.edit(view=touchline_view)

            # 10. Generate MatchResult and rewards
            if state.home_score > state.away_score:
                res_str = "win"
                coins_earned = 150
                points_earned = 3
            elif state.home_score == state.away_score:
                res_str = "draw"
                coins_earned = 50
                points_earned = 1
            else:
                res_str = "loss"
                coins_earned = 0
                points_earned = 0

            result = MatchResult(
                result=res_str,
                goals_for=state.home_score,
                goals_against=state.away_score,
                my_rating=my_rating,
                opponent_rating=opp_rating,
                coins_earned=coins_earned,
                points_earned=points_earned,
                possession_home=random.randint(45, 55),
                possession_away=random.randint(45, 55),
                shots_home=max(state.home_score + 1, random.randint(5, 12)),
                shots_away=max(state.away_score + 1, random.randint(5, 12)),
                motm=random.choice(match_cards).name
            )

            # 11. Transaction Safety: Sequential Database Updates
            new_energy = player["energy"] - 10
            new_coins = player["coins"] + result.coins_earned
            new_points = player["league_points"] + result.points_earned
            new_gd = player["goal_difference"] + (result.goals_for - result.goals_against)
            new_matches_played = player["matches_played"] + 1

            new_wins = player["wins"] + (1 if result.result == "win" else 0)
            new_draws = player["draws"] + (1 if result.result == "draw" else 0)
            new_losses = player["losses"] + (1 if result.result == "loss" else 0)

            # Write club standings
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

            # Insert history
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

            # Atomically update player card XP, evolution tracks, and morale
            card_ids = [c["id"] for c in active_cards]
            await db.rpc("process_match_result", {
                "p_result": result.result,
                "p_card_ids": card_ids,
                "p_xp_amount": 15
            }).execute()

            # 12. Send Post-Match Press Conference UI
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
            
            press_embed.set_footer(text="✅ Rewards, XP gains, and evolutions saved to database.")
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

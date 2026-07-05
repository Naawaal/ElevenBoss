# apps/discord_bot/cogs/battle_cog.py
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
    CommentaryEngine,
    MatchState,
    stream_match,
    MatchResult
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed

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

    @discord.ui.button(style=discord.ButtonStyle.danger, label="⚔️ Attack", custom_id="battle_touchline_attack")
    async def attack_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 1.3
        await interaction.response.send_message("📣 **Touchline**: Tactical focus shifted to **Attack**!", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⚖️ Balanced", custom_id="battle_touchline_balanced")
    async def balanced_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 1.0
        await interaction.response.send_message("📣 **Touchline**: Tactics set to **Balanced** shape.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🛡️ Defend", custom_id="battle_touchline_defend")
    async def defend_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 0.7
        await interaction.response.send_message("📣 **Touchline**: Tactical focus shifted to **Defend**!", ephemeral=True)

class ArenaHubView(discord.ui.View):
    def __init__(self, cog: BattleCog, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.danger, label="🤖 Bot Battle", custom_id="arena_bot_battle")
    async def bot_battle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer ephemeral button click response
        await interaction.response.defer(ephemeral=True)
        # Programmatically execute bot battle simulation
        await self.cog.execute_bot_battle(interaction)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🤝 Friendly Match (Soon)", custom_id="arena_friendly", disabled=True)
    async def friendly_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🏆 Ranked (Soon)", custom_id="arena_ranked", disabled=True)
    async def ranked_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

class BattleCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    battle_group = app_commands.Group(name="battle", description="Competitive Battle Arena.", guild_only=True)

    @battle_group.command(name="hub", description="Open the Battle Arena Hub.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def battle_hub(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        db = await get_client()
        player_res = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
        player = player_res.data

        embed = discord.Embed(
            title="🏟️ ElevenBoss Battle Arena",
            description=(
                f"Welcome to the Battle Arena, Manager **{player['manager_name']}**!\n"
                f"Choose your competitive match pathway below. Bot battles consume ⚡ 10 energy."
            ),
            color=0x00FF87
        )
        view = ArenaHubView(self, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @battle_group.command(name="bot", description="Simulate a league match against a division-calibrated AI opponent.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def battle_bot(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False)
        await self.execute_bot_battle(interaction)

    async def execute_bot_battle(self, interaction: discord.Interaction) -> None:
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

            # 6. Post Match Ticket
            ticket_embed = discord.Embed(
                title=f"🎫 Match Ticket: {player['club_name']} vs {opp_name}",
                description="A new league match has kicked off! Live commentary is streaming now.",
                color=0x00FF87
            )
            ticket_embed.add_field(name="Division", value=player["division"], inline=True)
            ticket_embed.add_field(name="Cost", value="⚡ 10 Energy", inline=True)
            
            # Post using followup or channel depending on invocation source
            if interaction.response.is_done():
                ticket_msg = await interaction.channel.send(embed=ticket_embed)
            else:
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

            # 8. Send Initial Live Match Embed
            init_embed = discord.Embed(
                title=f"🏟️ Live Stadium: {player['club_name']} vs {opp_name}",
                color=0x00FF87
            )
            init_embed.add_field(name="Scoreboard", value=f"🏟️ **{player['club_name']}** `0 - 0` **{opp_name}**", inline=False)
            init_embed.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
            init_embed.add_field(name="Commentary Ticker", value="🟢 **0'** - The referee blows the whistle and we are underway!", inline=False)

            touchline_view = TouchlineView(state, interaction.user.id)
            ticker_msg = await target.send(embed=init_embed, view=touchline_view)

            opp_squad = [
                MatchPlayerCard(name="Opponent Striker", position="FWD", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Midfielder", position="MID", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Defender", position="DEF", overall=int(opp_rating)),
            ]

            # 9. Commentary Streaming Loop
            ticker_history: list[str] = []
            
            async for ev in stream_match(state, match_cards, opp_squad, player["club_name"], opp_name):
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

                embed = discord.Embed(
                    title=f"🏟️ Live Stadium: {player['club_name']} vs {opp_name}",
                    color=0x00FF87
                )
                embed.add_field(name="Scoreboard", value=f"🏟️ **{player['club_name']}** `{ev['score_update']}` **{opp_name}**", inline=False)
                embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
                embed.add_field(name="Commentary Ticker", value="\n".join(recent_ticker), inline=False)

                await ticker_msg.edit(embed=embed, view=touchline_view)

                if ev["type"] == "FULL_TIME":
                    sleep_time = 2.0
                elif urgency == "cliffhanger":
                    sleep_time = 3.5
                elif urgency == "build_up":
                    sleep_time = 2.5
                else:
                    sleep_time = 1.5

                await asyncio.sleep(sleep_time)

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

            # 11. Transaction Safety Payouts
            new_energy = player["energy"] - 10
            new_coins = player["coins"] + result.coins_earned
            new_points = player["league_points"] + result.points_earned
            new_gd = player["goal_difference"] + (result.goals_for - result.goals_against)
            new_matches_played = player["matches_played"] + 1

            new_wins = player["wins"] + (1 if result.result == "win" else 0)
            new_draws = player["draws"] + (1 if result.result == "draw" else 0)
            new_losses = player["losses"] + (1 if result.result == "loss" else 0)

            # Write standings updates
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

            # 12. Send Post-Match Press Conference
            press_embed = discord.Embed(
                title="🎙️ Post-Match Press Conference",
                description="Reporters gather as the managers discuss the game statistics and performance.",
                color=0xFFCC00
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

            # 13. Thread archive task
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
            # Use appropriate error delivery channel
            if interaction.response.is_done():
                await interaction.channel.send(embed=error_embed(f"An error occurred: {str(e)}"))
            else:
                await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

    async def execute_league_match(self, interaction: discord.Interaction, fixture: dict) -> None:
        try:
            db = await get_client()
            user_id = interaction.user.id
            fixture_id = fixture["id"]
            
            # Re-fetch fixture to make sure it's not already played
            f_res = await db.table("league_fixtures").select("*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)").eq("id", fixture_id).maybe_single().execute()
            f = f_res.data
            if not f:
                await interaction.followup.send(embed=error_embed("Fixture not found."), ephemeral=True)
                return
                
            if f["is_played"]:
                await interaction.followup.send(embed=error_embed("This fixture has already been played."), ephemeral=True)
                return
                
            # Verify user is home or away team manager
            if user_id not in [f["home_team_id"], f["away_team_id"]]:
                await interaction.followup.send(embed=error_embed("You are not a manager in this fixture."), ephemeral=True)
                return
                
            # Fetch active player metadata (the one who triggered the match)
            active_p_res = await db.table("players").select("*").eq("discord_id", user_id).maybe_single().execute()
            active_p = active_p_res.data
            if not active_p:
                await interaction.followup.send(embed=error_embed("Active player profile not found."), ephemeral=True)
                return
                
            if active_p["energy"] < 10:
                await interaction.followup.send(
                    embed=error_embed(f"Insufficient energy. Matches require **10 energy**, but you only have **{active_p['energy']}**."),
                    ephemeral=True
                )
                return
                
            # Get home and away players
            home_p = f["home"]
            away_p = f["away"]
            
            # Load squads & ratings
            # --- HOME SQUAD ---
            home_squad = []
            home_rating = 60.0
            home_cards = []
            if home_p["is_ai"]:
                home_rating = float(home_p.get("ai_rating") or 60.0)
                home_squad = [
                    MatchPlayerCard(name="Opponent Striker", position="FWD", overall=int(home_rating)),
                    MatchPlayerCard(name="Opponent Midfielder", position="MID", overall=int(home_rating)),
                    MatchPlayerCard(name="Opponent Defender", position="DEF", overall=int(home_rating)),
                ]
            else:
                # Fetch squad assignments
                assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", f["home_team_id"]).execute()
                assignments = assignments_res.data or []
                home_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
                if len(home_cards) != 11:
                    await interaction.followup.send(
                        embed=error_embed(f"Home team (**{home_p['club_name']}**) does not have a valid starting squad (current: {len(home_cards)}/11 players)."),
                        ephemeral=True
                    )
                    return
                # Build MatchPlayerCards
                for c in home_cards:
                    ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", c["id"]).execute()
                    playstyles = [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []
                    home_squad.append(
                        MatchPlayerCard(
                            name=c["name"], position=c["position"], overall=c["overall"],
                            pac=c.get("pac", 50), sho=c.get("sho", 50), pas=c.get("pas", 50),
                            dri=c.get("dri", 50), def_stat=c.get("def", 50), phy=c.get("phy", 50),
                            morale=c.get("morale", 80), playstyles=playstyles
                        )
                    )
                home_rating = sum(p.overall for p in home_squad) / len(home_squad)
                
            # --- AWAY SQUAD ---
            away_squad = []
            away_rating = 60.0
            away_cards = []
            if away_p["is_ai"]:
                away_rating = float(away_p.get("ai_rating") or 60.0)
                away_squad = [
                    MatchPlayerCard(name="Opponent Striker", position="FWD", overall=int(away_rating)),
                    MatchPlayerCard(name="Opponent Midfielder", position="MID", overall=int(away_rating)),
                    MatchPlayerCard(name="Opponent Defender", position="DEF", overall=int(away_rating)),
                ]
            else:
                assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", f["away_team_id"]).execute()
                assignments = assignments_res.data or []
                away_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
                if len(away_cards) != 11:
                    await interaction.followup.send(
                        embed=error_embed(f"Away team (**{away_p['club_name']}**) does not have a valid starting squad (current: {len(away_cards)}/11 players)."),
                        ephemeral=True
                    )
                    return
                # Build MatchPlayerCards
                for c in away_cards:
                    ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", c["id"]).execute()
                    playstyles = [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []
                    away_squad.append(
                        MatchPlayerCard(
                            name=c["name"], position=c["position"], overall=c["overall"],
                            pac=c.get("pac", 50), sho=c.get("sho", 50), pas=c.get("pas", 50),
                            dri=c.get("dri", 50), def_stat=c.get("def", 50), phy=c.get("phy", 50),
                            morale=c.get("morale", 80), playstyles=playstyles
                        )
                    )
                away_rating = sum(p.overall for p in away_squad) / len(away_squad)
                
            # Instantiate V2 MatchState and CommentaryEngine
            state = MatchState(home_rating=home_rating, away_rating=away_rating)
            commentary_engine = CommentaryEngine()
            
            home_name = home_p["club_name"] + (" (AI)" if home_p["is_ai"] else "")
            away_name = away_p["club_name"] + (" (AI)" if away_p["is_ai"] else "")
            
            # Post Match Ticket
            ticket_embed = discord.Embed(
                title=f"🎫 League Match Ticket: {home_name} vs {away_name}",
                description=f"A league match has kicked off! Live commentary is streaming now.",
                color=0x00FF87
            )
            ticket_embed.add_field(name="Matchday", value=f"Matchday {f['matchday']}", inline=True)
            ticket_embed.add_field(name="Cost", value="⚡ 10 Energy", inline=True)
            
            # Post using followup or channel depending on invocation source
            if interaction.response.is_done():
                ticket_msg = await interaction.channel.send(embed=ticket_embed)
            else:
                ticket_msg = await interaction.followup.send(embed=ticket_embed)
                
            # Spawn Live Stadium public thread
            thread = None
            if interaction.guild and hasattr(interaction.channel, "create_thread"):
                try:
                    thread = await interaction.channel.create_thread(
                        name=f"🏟️ {home_name} vs {away_name} - Live",
                        message=ticket_msg,
                        auto_archive_duration=60
                    )
                except Exception as e:
                    logger.warning(f"Failed to create public match thread: {e}. Falling back to main channel.")
                    
            if thread:
                ticket_embed.add_field(name="Stadium Thread", value=thread.mention, inline=False)
                await ticket_msg.edit(embed=ticket_embed)
                
            target = thread if thread else interaction.channel
            
            # Send Initial Live Match Embed
            init_embed = discord.Embed(
                title=f"🏟️ Live Stadium: {home_name} vs {away_name}",
                color=0x00FF87
            )
            init_embed.add_field(name="Scoreboard", value=f"🏟️ **{home_name}** `0 - 0` **{away_name}**", inline=False)
            init_embed.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
            init_embed.add_field(name="Commentary Ticker", value="🟢 **0'** - The referee blows the whistle and we are underway!", inline=False)
            
            touchline_view = TouchlineView(state, user_id)
            ticker_msg = await target.send(embed=init_embed, view=touchline_view)
            
            # Commentary Streaming Loop
            ticker_history: list[str] = []
            
            async for ev in stream_match(state, home_squad, away_squad, home_name, away_name):
                variables = {"actor": ev["actor"], "team": ev["team"]}
                comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
                text = comm["text"]
                urgency = comm["urgency"]
                
                emoji_map = {
                    "KICKOFF": "🟢", "GOAL": "⚽", "MISS": "❌",
                    "CHANCE": "🎯", "FOUL": "🟨", "FULL_TIME": "🏁"
                }
                emo = emoji_map.get(ev["type"], "⏱️")
                
                ticker_history.append(f"{emo} **{ev['minute']}'** - {text}")
                recent_ticker = ticker_history[-5:]
                
                embed = discord.Embed(
                    title=f"🏟️ Live Stadium: {home_name} vs {away_name}",
                    color=0x00FF87
                )
                embed.add_field(name="Scoreboard", value=f"🏟️ **{home_name}** `{ev['score_update']}` **{away_name}**", inline=False)
                embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
                embed.add_field(name="Commentary Ticker", value="\n".join(recent_ticker), inline=False)
                
                await ticker_msg.edit(embed=embed, view=touchline_view)
                
                if ev["type"] == "FULL_TIME":
                    sleep_time = 2.0
                elif urgency == "cliffhanger":
                    sleep_time = 3.5
                elif urgency == "build_up":
                    sleep_time = 2.5
                else:
                    sleep_time = 1.5
                    
                await asyncio.sleep(sleep_time)
                
            for child in touchline_view.children:
                child.disabled = True
            await ticker_msg.edit(view=touchline_view)
            
            # Payout rewards and write match results
            # Deduct energy from active player
            await db.table("players").update({"energy": active_p["energy"] - 10}).eq("discord_id", user_id).execute()
            
            # Log results in league_fixtures table
            await db.table("league_fixtures").update({
                "home_score": state.home_score,
                "away_score": state.away_score,
                "is_played": True,
                "played_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", fixture_id).execute()
            
            # Process Home side rewards/career stats
            home_result_str = "win" if state.home_score > state.away_score else ("draw" if state.home_score == state.away_score else "loss")
            home_coins = 150 if home_result_str == "win" else (50 if home_result_str == "draw" else 0)
            home_pts = 3 if home_result_str == "win" else (1 if home_result_str == "draw" else 0)
            
            if not home_p["is_ai"]:
                await db.table("players").update({
                    "coins": home_p["coins"] + home_coins,
                    "league_points": home_p["league_points"] + home_pts,
                    "goal_difference": home_p["goal_difference"] + (state.home_score - state.away_score),
                    "matches_played": home_p["matches_played"] + 1,
                    "wins": home_p["wins"] + (1 if home_result_str == "win" else 0),
                    "draws": home_p["draws"] + (1 if home_result_str == "draw" else 0),
                    "losses": home_p["losses"] + (1 if home_result_str == "loss" else 0)
                }).eq("discord_id", f["home_team_id"]).execute()
                # Insert history
                await db.table("match_history").insert({
                    "player_id": f["home_team_id"], "result": home_result_str, "my_rating": home_rating,
                    "opponent_rating": away_rating, "goals_for": state.home_score, "goals_against": state.away_score,
                    "coins_earned": home_coins, "points_earned": home_pts
                }).execute()
                # Update player cards XP/morale
                c_ids = [c["id"] for c in home_cards]
                await db.rpc("process_match_result", {"p_result": home_result_str, "p_card_ids": c_ids, "p_xp_amount": 15}).execute()
                
            # Process Away side rewards/career stats
            away_result_str = "win" if state.away_score > state.home_score else ("draw" if state.home_score == state.away_score else "loss")
            away_coins = 150 if away_result_str == "win" else (50 if away_result_str == "draw" else 0)
            away_pts = 3 if away_result_str == "win" else (1 if away_result_str == "draw" else 0)
            
            if not away_p["is_ai"]:
                await db.table("players").update({
                    "coins": away_p["coins"] + away_coins,
                    "league_points": away_p["league_points"] + away_pts,
                    "goal_difference": away_p["goal_difference"] + (state.away_score - state.home_score),
                    "matches_played": away_p["matches_played"] + 1,
                    "wins": away_p["wins"] + (1 if away_result_str == "win" else 0),
                    "draws": away_p["draws"] + (1 if away_result_str == "draw" else 0),
                    "losses": away_p["losses"] + (1 if away_result_str == "loss" else 0)
                }).eq("discord_id", f["away_team_id"]).execute()
                # Insert history
                await db.table("match_history").insert({
                    "player_id": f["away_team_id"], "result": away_result_str, "my_rating": away_rating,
                    "opponent_rating": home_rating, "goals_for": state.away_score, "goals_against": state.home_score,
                    "coins_earned": away_coins, "points_earned": away_pts
                }).execute()
                # Update player cards XP/morale
                c_ids = [c["id"] for c in away_cards]
                await db.rpc("process_match_result", {"p_result": away_result_str, "p_card_ids": c_ids, "p_xp_amount": 15}).execute()
                
            # Check matchday advancement
            from apps.discord_bot.cogs.league_cog import update_current_matchday
            await update_current_matchday(db, f["season_id"])
            
            # Send Post-Match Press Conference
            press_embed = discord.Embed(
                title="🎙️ Post-Match Press Conference",
                description="Reporters gather as the managers discuss the game statistics and performance.",
                color=0xFFCC00
            )
            
            result_emoji = "🎉 HOME WIN" if state.home_score > state.away_score else ("🎉 AWAY WIN" if state.away_score > state.home_score else "🤝 DRAW")
            
            press_embed.add_field(
                name="🥅 Final Result",
                value=f"### {result_emoji}\n**{home_name}** `{state.home_score} - {state.away_score}` **{away_name}**",
                inline=False
            )
            
            # MOTM
            all_human_cards = home_squad if not home_p["is_ai"] else (away_squad if not away_p["is_ai"] else [])
            motm = random.choice(all_human_cards).name if all_human_cards else "AI Match MVP"
            
            press_embed.add_field(
                name="📊 Match Statistics",
                value=(
                    f"**Possession**: {state.home_score * 3 + 45}% - {100 - (state.home_score * 3 + 45)}%\n"
                    f"**Shots**: {state.home_score + random.randint(3, 8)} - {state.away_score + random.randint(3, 8)}\n"
                    f"**Man of the Match**: ⭐ **{motm}**"
                ),
                inline=True
            )
            
            active_earned = home_coins if user_id == f["home_team_id"] else away_coins
            active_pts = home_pts if user_id == f["home_team_id"] else away_pts
            
            press_embed.add_field(
                name="🎁 Your Rewards",
                value=(
                    f"🪙 **+{active_earned} coins**\n"
                    f"🏆 **+{active_pts} league pts**"
                ),
                inline=True
            )
            press_embed.set_footer(text="✅ Rewards, XP gains, and league standings saved to database.")
            await target.send(embed=press_embed)
            
            # Thread renaming and archiving
            if thread:
                try:
                    await thread.edit(name=f"🏆 {home_name} {state.home_score}-{state.away_score} {away_name}")
                except Exception as e:
                    logger.warning(f"Failed to rename thread: {e}")
                    
                async def archive_thread_after_delay(t: discord.Thread, delay: float) -> None:
                    await asyncio.sleep(delay)
                    try:
                        await t.edit(locked=True, archived=True)
                    except discord.NotFound:
                        pass
                    except Exception as err:
                        logger.warning(f"Failed to lock and archive thread {t.id}: {err}")
                        
                asyncio.create_task(archive_thread_after_delay(thread, 180.0))
                
        except Exception as e:
            logger.exception("Failed to execute league match.")
            if interaction.response.is_done():
                await interaction.channel.send(embed=error_embed(f"An error occurred: {str(e)}"))
            else:
                await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))

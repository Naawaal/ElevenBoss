# apps/discord_bot/cogs/league_cog.py
from __future__ import annotations
import logging
import asyncio
import random
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from match_engine import generate_round_robin_fixtures, simulate_match, MatchInput, MatchPlayerCard
from apps.discord_bot.core.locks import get_guild_thread_lock

logger = logging.getLogger(__name__)

BOT_NAMES = [
    "Local Pub FC", "Sunday League United", "Park Wanderers", "Metro Athletic",
    "Town Rovers", "Suburban City", "County Rangers", "District FC",
    "State Alliance", "Apex Rovers", "Vanguard City", "Dynamo FC",
    "Zenith United", "Sovereign Athletic", "Majestic FC", "Titan Legends",
    "Antigravity FC", "Grandmasters United"
]

# --- STANDINGS HELPER ---
async def fetch_standings(db, season_id: str) -> list[dict]:
    """
    Fetch aggregated standings for the given season.
    Sort order: Points DESC, Goal Difference DESC, Goals For DESC, Username ASC.
    """
    parts_res = await db.table("league_participants").select("*, players(*)").eq("season_id", season_id).execute()
    participants = parts_res.data or []
    
    fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season_id).eq("is_played", True).execute()
    fixtures = fixtures_res.data or []
    
    standings = []
    for part in participants:
        player = part["players"]
        pid = player["discord_id"]
        
        wins = 0
        draws = 0
        losses = 0
        goals_for = 0
        goals_against = 0
        matches_played = 0
        
        for f in fixtures:
            if f["home_team_id"] == pid:
                matches_played += 1
                goals_for += f["home_score"]
                goals_against += f["away_score"]
                if f["home_score"] > f["away_score"]:
                    wins += 1
                elif f["home_score"] == f["away_score"]:
                    draws += 1
                else:
                    losses += 1
            elif f["away_team_id"] == pid:
                matches_played += 1
                goals_for += f["away_score"]
                goals_against += f["home_score"]
                if f["away_score"] > f["home_score"]:
                    wins += 1
                elif f["away_score"] == f["home_score"]:
                    draws += 1
                else:
                    losses += 1
                    
        points = wins * 3 + draws * 1
        gd = goals_for - goals_against
        
        standings.append({
            "discord_id": pid,
            "username": player["username"],
            "club_name": player["club_name"] or f"Club {pid}",
            "manager_name": player["manager_name"] or "Unknown",
            "is_ai": player.get("is_ai", False),
            "ai_rating": player.get("ai_rating"),
            "is_active": part.get("is_active", True),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "matches_played": matches_played,
            "points": points,
            "goal_difference": gd
        })
        
    standings.sort(key=lambda x: (x["points"], x["goal_difference"], x["goals_for"], -x["discord_id"]), reverse=True)
    return standings


# --- AUTO SIMULATION OF EXPIRED MATCHDAY WINDOWS ---
async def auto_sim_expired_fixtures(db, season_id: str, bot: commands.Bot) -> int:
    """
    Scans for unplayed fixtures of the season where window_end has passed,
    and runs simulation sequentially via run_league_match_simulation.
    """
    now = datetime.now(timezone.utc)
    # Query fixtures
    fixtures_res = await db.table("league_fixtures").select("*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)").eq("season_id", season_id).eq("is_played", False).execute()
    fixtures = fixtures_res.data or []
    
    # Get guild_id
    season_res = await db.table("league_seasons").select("league_id").eq("id", season_id).maybe_single().execute()
    season_data = season_res.data if season_res else None
    if not season_data:
        return 0
    league_id = season_data["league_id"]
    
    league_res = await db.table("leagues").select("guild_id").eq("id", league_id).maybe_single().execute()
    league_data = league_res.data if league_res else None
    if not league_data:
        return 0
    guild_id = league_data["guild_id"]
    
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.warning(f"Guild {guild_id} not found/cached by bot.")
        return 0
        
    # Resolve thread (with concurrency lock)
    logger.info(f"[Trace] [auto_sim_expired_fixtures] Auto-sim match checking/creation requested for guild {guild_id}. Requesting lock...")
    
    lock = await get_guild_thread_lock(guild_id)
    async with lock:
        logger.info(f"[Trace] [auto_sim_expired_fixtures] Lock acquired for guild {guild_id}.")
        config_res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
        config = config_res.data if config_res else None
        
        league_channel_id = config.get("league_channel_id") if config else None
        league_updates_thread_id = config.get("league_updates_thread_id") if config else None
        
        logger.info(f"[Trace] [auto_sim_expired_fixtures] DB thread check: league_updates_thread_id={league_updates_thread_id}")

        if not league_channel_id:
            logger.warning(f"league_channel_id not configured for guild {guild_id}")
            return 0
            
        announcement_channel = guild.get_channel(league_channel_id)
        if not announcement_channel:
            logger.warning(f"announcement_channel {league_channel_id} not found in guild {guild_id}")
            return 0
            
        thread = None
        if league_updates_thread_id:
            thread = guild.get_thread(league_updates_thread_id)
            logger.info(f"[Trace] [auto_sim_expired_fixtures] Cache check for thread {league_updates_thread_id}: thread_found={thread is not None}")
            if not thread:
                try:
                    thread = await guild.fetch_channel(league_updates_thread_id)
                    logger.info(f"[Trace] [auto_sim_expired_fixtures] API fetch check for thread {league_updates_thread_id}: thread_found={thread is not None}")
                except discord.NotFound:
                    logger.warning(f"[Trace] [auto_sim_expired_fixtures] API fetch failed: thread {league_updates_thread_id} NotFound.")
                    thread = None
                except Exception as e:
                    logger.error(f"[Trace] [auto_sim_expired_fixtures] API fetch failed with error: {e}")
                    thread = None

        if not thread:
            logger.info(f"[Trace] [auto_sim_expired_fixtures] Thread is missing or invalid. Initiating thread creation in channel {league_channel_id}...")
            try:
                thread = await announcement_channel.create_thread(
                    name="📰 league-journal",
                    type=discord.ChannelType.public_thread,
                    auto_archive_duration=60
                )
                logger.info(f"[Trace] [auto_sim_expired_fixtures] Thread created successfully with ID {thread.id}. Posting intro rules...")
                info_embed = discord.Embed(
                    title="🏆 ElevenBoss League Journal",
                    description=(
                        "Welcome to the official League Journal! Here you will find live match tickers, "
                        "results, and season summaries.\n\n"
                        "**League Rules & Info:**\n"
                        "• Play matches using `/league hub` before the matchday window ends.\n"
                        "• Unplayed matches will be auto-simulated at the end of the window.\n"
                        "• Win = 3 pts, Draw = 1 pt, Loss = 0 pts."
                    ),
                    color=0x00FF87
                )
                first_msg = await thread.send(embed=info_embed)
                try:
                    await first_msg.pin()
                except Exception as pe:
                    logger.warning(f"Failed to pin introductory message in thread {thread.id}: {pe}")
                
                try:
                    everyone_role = announcement_channel.guild.default_role
                    overwrites = announcement_channel.overwrites_for(everyone_role)
                    if overwrites.add_reactions != True:
                        overwrites.add_reactions = True
                        await announcement_channel.set_permissions(everyone_role, overwrite=overwrites)
                        logger.info(f"Enabled add_reactions permissions for @everyone on parent channel {announcement_channel.id}")
                except Exception as pe:
                    logger.warning(f"Could not adjust parent channel reaction permissions: {pe}")

                logger.info(f"[Trace] [auto_sim_expired_fixtures] Saving thread ID {thread.id} to guild_config...")
                await db.table("guild_config").update({"league_updates_thread_id": thread.id}).eq("guild_id", guild_id).execute()
                logger.info(f"[Trace] [auto_sim_expired_fixtures] Thread ID {thread.id} successfully confirmed in DB.")
            except Exception as e:
                logger.exception("Failed to create League Journal thread in auto-sim.")
                return 0
        else:
            logger.info(f"[Trace] [auto_sim_expired_fixtures] Reusing existing thread {thread.id}.")

    logger.info(f"[Trace] [auto_sim_expired_fixtures] Released lock for guild {guild_id}.")

    from apps.discord_bot.cogs.battle_cog import run_league_match_simulation, LeagueMatchHandler

    simulated_count = 0
    for f in fixtures:
        window_end_val = f.get("window_end")
        if not window_end_val:
            continue
        window_end = datetime.fromisoformat(window_end_val.replace("Z", "+00:00"))
        if now > window_end:
            try:
                handler = LeagueMatchHandler(thread, fixture_id=f["id"], season_id=f["season_id"])
                await run_league_match_simulation(
                    bot=bot,
                    db=db,
                    guild=guild,
                    fixture=f,
                    active_player_id=None,
                    handler=handler
                )
                simulated_count += 1
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.exception(f"Failed to auto-simulate fixture {f['id']}: {e}")
                
    if simulated_count > 0:
        await update_current_matchday(db, season_id)
        
    return simulated_count

async def update_current_matchday(db, season_id: str):
    """Checks if all fixtures of current matchday are played, and increments current_matchday."""
    season_res = await db.table("league_seasons").select("*").eq("id", season_id).maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        return
        
    curr = season["current_matchday"]
    total = season["total_matchdays"]
    
    unplayed_res = await db.table("league_fixtures").select("id").eq("season_id", season_id).eq("matchday", curr).eq("is_played", False).execute()
    if not unplayed_res.data:
        if curr < total:
            await db.table("league_seasons").update({"current_matchday": curr + 1}).eq("id", season_id).execute()
            logger.info(f"Season {season_id} advanced to matchday {curr + 1}")
        else:
            await db.table("league_seasons").update({
                "status": "completed",
                "end_time": datetime.now(timezone.utc).isoformat()
            }).eq("id", season_id).execute()
            
            league_res = await db.table("leagues").select("guild_id").eq("id", season["league_id"]).maybe_single().execute()
            if league_res and league_res.data:
                await db.table("guild_config").update({"league_status": "inactive"}).eq("guild_id", league_res.data["guild_id"]).execute()
            logger.info(f"Season {season_id} has been fully completed!")


# --- VIEWS ---

class BaseLeagueView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another manager.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                embed = self.message.embeds[0]
                embed.set_footer(text="Session timed out. Run /league hub to restart.")
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass


class LeagueHubView(BaseLeagueView):
    def __init__(self, cog: LeagueCog, owner_id: int, guild_id: int) -> None:
        super().__init__(owner_id)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(style=discord.ButtonStyle.success, label="📝 Register", custom_id="hub_register_btn", row=0)
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.player_register_league(interaction)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="📊 Standings", custom_id="hub_view_table_btn", row=0)
    async def view_table_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_standings(interaction, self)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⚽ My Fixtures", custom_id="hub_my_fixtures_btn", row=0)
    async def my_fixtures_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_fixtures(interaction, self)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="👟 Player Stats", custom_id="hub_season_stats_btn", row=0)
    async def season_stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_stats(interaction, self)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="📺 Match Center", custom_id="hub_match_center_btn", row=1)
    async def match_center_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_match_center(interaction, self)



class StandingsView(BaseLeagueView):
    def __init__(self, cog: LeagueCog, owner_id: int, parent_view: LeagueHubView) -> None:
        super().__init__(owner_id)
        self.cog = cog
        self.parent_view = parent_view

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", custom_id="standings_back")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_hub(interaction, self.parent_view)


class FixturesView(BaseLeagueView):
    def __init__(self, cog: LeagueCog, owner_id: int, parent_view: LeagueHubView, fixture: dict | None = None) -> None:
        super().__init__(owner_id)
        self.cog = cog
        self.parent_view = parent_view
        self.fixture = fixture
        
        if not fixture:
            for child in list(self.children):
                if child.custom_id == "fixtures_play":
                    self.remove_item(child)

    @discord.ui.button(style=discord.ButtonStyle.danger, label="⚔️ Play Match", custom_id="fixtures_play", row=0)
    async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)
        await self.cog.play_league_match(interaction, self.fixture)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", custom_id="fixtures_back", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_hub(interaction, self.parent_view)


class StatsView(BaseLeagueView):
    def __init__(self, cog: LeagueCog, owner_id: int, parent_view: LeagueHubView) -> None:
        super().__init__(owner_id)
        self.cog = cog
        self.parent_view = parent_view

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", custom_id="stats_back")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_hub(interaction, self.parent_view)


class MatchCenterSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="Select a completed match to view box score...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="match_center_fixture_select"
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        fixture_id = self.values[0]
        view: MatchCenterView = self.view
        await view.cog.show_box_score(interaction, fixture_id, view)


class MatchCenterView(BaseLeagueView):
    def __init__(self, cog: LeagueCog, owner_id: int, parent_view: LeagueHubView, select_options: list[discord.SelectOption]) -> None:
        super().__init__(owner_id)
        self.cog = cog
        self.parent_view = parent_view
        
        if select_options:
            self.add_item(MatchCenterSelect(select_options))

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Hub", custom_id="match_center_back", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_hub(interaction, self.parent_view)



# --- COG CLASS ---

class LeagueCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    league_group = app_commands.Group(name="league", description="View seasonal league standing & fixtures.", guild_only=True)

    @league_group.command(name="hub", description="Open the Server League Hub dashboard.")
    @app_commands.guild_only()
    async def league_hub(self, interaction: discord.Interaction) -> None:
        """Slash command to open the Seasonal League Hub."""
        await interaction.response.defer(ephemeral=True)
        
        db = await get_client()
        guild_id = interaction.guild_id
        
        # Verify guild config, create if not exists
        config_res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
        config = config_res.data if config_res else None
        if not config:
            await db.table("guild_config").insert({"guild_id": guild_id}).execute()
            config_res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
            config = config_res.data if config_res else None
            
        league_res = await db.table("leagues").select("*").eq("guild_id", guild_id).maybe_single().execute()
        league = league_res.data if league_res else None
        
        season = None
        if league:
            season_res = await db.table("league_seasons").select("*").eq("league_id", league["id"]).eq("status", "active").maybe_single().execute()
            season = season_res.data if season_res else None
            
        if season:
            await auto_sim_expired_fixtures(db, season["id"], self.bot)
            season_res = await db.table("league_seasons").select("*").eq("id", season["id"]).maybe_single().execute()
            season = season_res.data if season_res else None

        embed = await self.build_hub_embed(interaction, league, season)
        view = LeagueHubView(self, interaction.user.id, guild_id)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg

    # --- VIEW ROUTINES ---

    async def show_hub(self, interaction: discord.Interaction, view: LeagueHubView):
        db = await get_client()
        league_res = await db.table("leagues").select("*").eq("guild_id", view.guild_id).maybe_single().execute()
        league = league_res.data if league_res else None
        season = None
        if league:
            season_res = await db.table("league_seasons").select("*").eq("league_id", league["id"]).eq("status", "active").maybe_single().execute()
            season = season_res.data if season_res else None
            
        if season:
            await auto_sim_expired_fixtures(db, season["id"], self.bot)
            season_res = await db.table("league_seasons").select("*").eq("id", season["id"]).maybe_single().execute()
            season = season_res.data if season_res else None

        embed = await self.build_hub_embed(interaction, league, season)
        await interaction.edit_original_response(embed=embed, view=view)

    async def show_match_center(self, interaction: discord.Interaction, hub_view: LeagueHubView):
        db = await get_client()
        league_res = await db.table("leagues").select("id").eq("guild_id", hub_view.guild_id).maybe_single().execute()
        if not league_res or not league_res.data:
            await interaction.edit_original_response(embed=error_embed("No league configured for this server."), view=hub_view)
            return
            
        season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            await interaction.edit_original_response(embed=error_embed("No active league season."), view=hub_view)
            return

        # Fetch completed fixtures for this season
        fixtures_res = await db.table("league_fixtures").select("*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)").eq("season_id", season["id"]).eq("is_played", True).execute()
        completed = fixtures_res.data or []

        user_matches = []
        global_matches = []
        user_id = interaction.user.id
        
        for f in completed:
            if user_id in [f["home_team_id"], f["away_team_id"]]:
                user_matches.append(f)
            else:
                global_matches.append(f)

        # Sort global matches by played_at descending
        global_matches.sort(key=lambda x: x.get("played_at") or "", reverse=True)
        global_subset = global_matches[:10]
        
        # Combine and remove duplicates
        combined = user_matches + [m for m in global_subset if m["id"] not in [u["id"] for u in user_matches]]
        combined.sort(key=lambda x: (x.get("matchday") or 0, x.get("played_at") or ""), reverse=True)
        
        dropdown_list = combined[:25]

        select_options = []
        for f in dropdown_list:
            home_name = f["home"]["club_name"] if f.get("home") else "Home Team"
            away_name = f["away"]["club_name"] if f.get("away") else "Away Team"
            label = f"Matchday {f['matchday']}: {home_name} vs {away_name}"
            if len(label) > 100:
                label = label[:97] + "..."
            description = f"Score: {f['home_score']} - {f['away_score']}"
            select_options.append(discord.SelectOption(
                label=label,
                value=f["id"],
                description=description
            ))

        embed = discord.Embed(
            title="📺 League Match Center",
            description=(
                "Select a completed fixture from the dropdown below to view its statistics, "
                "box score, and events timeline.\n\n"
                f"Showing **{len(select_options)}** completed matches."
            ),
            color=0x00FF87
        )
        if not select_options:
            embed.description = "No completed matches are available to view yet in this season."

        view = MatchCenterView(self, interaction.user.id, hub_view, select_options)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = hub_view.message

    async def show_box_score(self, interaction: discord.Interaction, fixture_id: str, view: MatchCenterView):
        db = await get_client()
        fixture_res = await db.table("league_fixtures").select("*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)").eq("id", fixture_id).maybe_single().execute()
        f = fixture_res.data if fixture_res else None
        if not f:
            await interaction.followup.send(embed=error_embed("Fixture not found."), ephemeral=True)
            return

        log_res = await db.table("match_logs").select("*").eq("fixture_id", fixture_id).maybe_single().execute()
        log = log_res.data if log_res else None
        
        home_name = f["home"]["club_name"] if f.get("home") else "Home Team"
        away_name = f["away"]["club_name"] if f.get("away") else "Away Team"

        embed = discord.Embed(
            title=f"📺 Match Center Box Score",
            color=0x00FF87
        )
        embed.add_field(
            name="🏟️ Final Score",
            value=f"### **{home_name}** `{f['home_score']} - {f['away_score']}` **{away_name}**\n*Matchday {f['matchday']}*",
            inline=False
        )

        if log:
            box = log.get("box_score") or {}
            events = log.get("key_events") or []
            
            embed.add_field(
                name="📊 Match Statistics",
                value=(
                    f"**Possession**: {box.get('possession_home', 50)}% - {box.get('possession_away', 50)}%\n"
                    f"**Shots**: {box.get('shots_home', 0)} - {box.get('shots_away', 0)}\n"
                    f"**Man of the Match**: ⭐ **{box.get('motm', 'TBD')}**"
                ),
                inline=True
            )
            
            timeline_lines = []
            emoji_map = {
                "KICKOFF": "🟢", "GOAL": "⚽", "MISS": "❌",
                "CHANCE": "🎯", "FOUL": "💥", "YELLOW_CARD": "🟨",
                "INJURY": "🩹", "FULL_TIME": "🏁"
            }
            for ev in events:
                emo = emoji_map.get(ev.get("type"), "⏱️")
                text = ev.get("text") or "An event occurred."
                if ev.get("type") == "GOAL" and "assister" in ev:
                    text += f" (Assist: {ev['assister']})"
                timeline_lines.append(f"{emo} **{ev.get('minute', 0)}'** - {text}")
            
            if timeline_lines:
                embed.add_field(
                    name="Timeline",
                    value="\n".join(timeline_lines),
                    inline=False
                )
            else:
                embed.add_field(name="Timeline", value="No events recorded.", inline=False)
        else:
            embed.description = "Detailed box score statistics are not available for this match."

        await interaction.edit_original_response(embed=embed, view=view)


    async def show_standings(self, interaction: discord.Interaction, hub_view: LeagueHubView):
        db = await get_client()
        league_res = await db.table("leagues").select("id").eq("guild_id", hub_view.guild_id).maybe_single().execute()
        if not league_res or not league_res.data:
            await interaction.edit_original_response(embed=error_embed("No league configured for this server."), view=hub_view)
            return
            
        season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            await interaction.edit_original_response(embed=error_embed("No active league season."), view=hub_view)
            return

        standings = await fetch_standings(db, season["id"])
        
        embed = discord.Embed(
            title=f"📊 League Standings — Season {season['season_number']}",
            color=0x00FF87
        )
        
        table_str = "Pos  Club                  P   W  D  L   GD  PTS\n"
        table_str += "-----------------------------------------------\n"
        for idx, row in enumerate(standings, 1):
            club = row["club_name"]
            if row.get("is_ai"):
                club += " (AI)"
            if not row.get("is_active"):
                club += " 💤"
            club = (club[:17] + "...") if len(club) > 20 else club
            
            line = f"{idx:<4} {club:<20} {row['matches_played']:<3} {row['wins']:<2} {row['draws']:<2} {row['losses']:<2} {row['goal_difference']:+3} {row['points']:>3}\n"
            table_str += line
            
        embed.description = f"```\n{table_str}```\n*💤 = Inactive Manager (Ghost Club)*"
        
        view = StandingsView(self, interaction.user.id, hub_view)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = hub_view.message

    async def show_fixtures(self, interaction: discord.Interaction, hub_view: LeagueHubView):
        db = await get_client()
        league_res = await db.table("leagues").select("id").eq("guild_id", hub_view.guild_id).maybe_single().execute()
        if not league_res or not league_res.data:
            await interaction.edit_original_response(embed=error_embed("No league configured for this server."), view=hub_view)
            return
            
        season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            await interaction.edit_original_response(embed=error_embed("No active league season."), view=hub_view)
            return

        curr = season["current_matchday"]
        fixtures_res = await db.table("league_fixtures").select("*, home:players!league_fixtures_home_team_id_fkey(username, club_name, is_ai), away:players!league_fixtures_away_team_id_fkey(username, club_name, is_ai)").eq("season_id", season["id"]).eq("matchday", curr).execute()
        fixtures = fixtures_res.data or []
        
        embed = discord.Embed(
            title=f"🗓️ Matchday {curr} Fixtures",
            description="Here are the pairings for the current matchday:",
            color=0x00FF87
        )
        
        playable_fixture = None
        now = datetime.now(timezone.utc)
        
        fixture_lines = []
        for f in fixtures:
            home_name = f["home"]["club_name"] + (" (AI)" if f["home"].get("is_ai") else "")
            away_name = f["away"]["club_name"] + (" (AI)" if f["away"].get("is_ai") else "")
            
            if f["is_played"]:
                status_str = f"**{f['home_score']} - {f['away_score']}** (Full Time)"
            else:
                window_start = datetime.fromisoformat(f["window_start"].replace("Z", "+00:00"))
                window_end = datetime.fromisoformat(f["window_end"].replace("Z", "+00:00"))
                
                if now < window_start:
                    status_str = f"Locked (Starts <t:{int(window_start.timestamp())}:R>)"
                elif now > window_end:
                    status_str = "Expired (Pending Auto-Sim)"
                else:
                    status_str = f"⏰ Active (Ends <t:{int(window_end.timestamp())}:R>)"
                    if interaction.user.id in [f["home_team_id"], f["away_team_id"]]:
                        playable_fixture = f
            
            fixture_lines.append(f"🏟️ **{home_name}** vs **{away_name}**\n↳ {status_str}")
            
        embed.description = "\n\n".join(fixture_lines)
        
        view = FixturesView(self, interaction.user.id, hub_view, playable_fixture)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = hub_view.message

    async def show_stats(self, interaction: discord.Interaction, hub_view: LeagueHubView):
        db = await get_client()
        league_res = await db.table("leagues").select("id").eq("guild_id", hub_view.guild_id).maybe_single().execute()
        if not league_res or not league_res.data:
            await interaction.edit_original_response(embed=error_embed("No league configured for this server."), view=hub_view)
            return
            
        season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            await interaction.edit_original_response(embed=error_embed("No active league season."), view=hub_view)
            return

        fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season["id"]).execute()
        fixtures = fixtures_res.data or []
        
        played = [f for f in fixtures if f["is_played"]]
        total_goals = sum(f["home_score"] + f["away_score"] for f in played)
        avg_goals = round(total_goals / len(played), 2) if played else 0.0
        
        embed = discord.Embed(
            title=f"🏅 Season {season['season_number']} Statistics Overview",
            color=0x00FF87
        )
        embed.description = (
            f"📊 **Total Matches**: {len(played)} / {len(fixtures)} played\n"
            f"⚽ **Total Goals Scored**: {total_goals} goals\n"
            f"📈 **Average Goals/Match**: {avg_goals}"
        )
        
        # Query player season stats
        stats_res = await db.table("player_season_stats").select("*, players(*)").eq("season_id", season["id"]).execute()
        stats_rows = stats_res.data or []
        
        # Top Goals
        top_goals = sorted(stats_rows, key=lambda x: x.get("goals", 0), reverse=True)[:5]
        goals_text = ""
        for idx, row in enumerate(top_goals, 1):
            manager = row.get("players", {}).get("manager_name") or f"Player {row['player_id']}"
            goals_text += f"**{idx}.** {manager} - {row['goals']} Goals\n"
        if not goals_text:
            goals_text = "No goals recorded yet."
        embed.add_field(name="👟 Top Scoring Players (Golden Boot)", value=goals_text, inline=False)

        # Top Assists
        top_assists = sorted(stats_rows, key=lambda x: x.get("assists", 0), reverse=True)[:5]
        assists_text = ""
        for idx, row in enumerate(top_assists, 1):
            manager = row.get("players", {}).get("manager_name") or f"Player {row['player_id']}"
            assists_text += f"**{idx}.** {manager} - {row['assists']} Assists\n"
        if not assists_text:
            assists_text = "No assists recorded yet."
        embed.add_field(name="🤝 Top Assisting Players", value=assists_text, inline=False)

        # Clean Sheets
        top_cs = sorted(stats_rows, key=lambda x: x.get("clean_sheets", 0), reverse=True)[:5]
        cs_text = ""
        for idx, row in enumerate(top_cs, 1):
            manager = row.get("players", {}).get("manager_name") or f"Player {row['player_id']}"
            cs_text += f"**{idx}.** {manager} - {row['clean_sheets']} Clean Sheets\n"
        if not cs_text:
            cs_text = "No clean sheets recorded yet."
        embed.add_field(name="🛡️ Top Players (Clean Sheets)", value=cs_text, inline=False)

        view = StatsView(self, interaction.user.id, hub_view)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = hub_view.message

    # --- PLAYER LEAGUE REGISTRATION ---
    async def player_register_league(self, interaction: discord.Interaction):
        db = await get_client()
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        # 1. Check if user has an ElevenBoss profile
        p_res = await db.table("players").select("*").eq("discord_id", user_id).maybe_single().execute()
        player = p_res.data if p_res else None
        if not player or player.get("is_ai"):
            await interaction.followup.send(embed=error_embed("❌ You do not have a club yet! Run `/register` to create one first."), ephemeral=True)
            return
            
        # 2. Check if already registered for this guild league
        reg_res = await db.table("league_members").select("*").eq("guild_id", guild_id).eq("player_id", user_id).maybe_single().execute()
        if reg_res and reg_res.data:
            await interaction.followup.send(embed=error_embed("⚠️ You are already registered for this server's league!"), ephemeral=True)
            return
            
        # 3. Register
        await db.table("league_members").insert({
            "guild_id": guild_id,
            "player_id": user_id
        }).execute()
        
        await interaction.followup.send(
            embed=success_embed(
                f"✅ **Successfully registered!**\n"
                f"Manager **{player['manager_name']}** of **{player['club_name']}** has joined "
                f"the league roster for the upcoming season."
            ),
            ephemeral=True
        )

    # --- MATCH ENGINE ROUTINE ---
    async def play_league_match(self, interaction: discord.Interaction, fixture: dict):
        battle_cog = self.bot.get_cog("BattleCog")
        if not battle_cog:
            await interaction.followup.send(embed=error_embed("Battle Arena module is currently unavailable."), ephemeral=True)
            return
        await battle_cog.execute_league_match(interaction, fixture)

    # --- HELPERS ---
    async def build_hub_embed(self, interaction: discord.Interaction, league: dict | None, season: dict | None) -> discord.Embed:
        guild = interaction.guild
        embed = discord.Embed(
            title=f"🏆 {guild.name} Seasonal League Hub",
            color=0x00FF87
        )
        
        # Count registered managers
        db = await get_client()
        regs_res = await db.table("league_members").select("player_id", count="exact").eq("guild_id", guild.id).execute()
        reg_count = regs_res.count if regs_res else 0
        
        if not season:
            embed.description = (
                "Welcome to the Seasonal League Hub!\n\n"
                "💤 **Status**: No active season.\n\n"
                "Click **`[ 📝 Register ]`** below to join the roster for the upcoming league season!\n"
                f"Current Registered Managers: **{reg_count}**\n\n"
                "*Server admins can start the season from the administrative /admin dashboard in DMs.*"
            )
            return embed
            
        standings = await fetch_standings(db, season["id"])
        
        curr = season["current_matchday"]
        total = season["total_matchdays"]
        
        embed.description = f"🟢 **Matchday {curr}/{total} Active**"
        
        standings_preview = "Pos  Club                  PTS   GD\n"
        standings_preview += "----------------------------------\n"
        for idx, row in enumerate(standings[:5], 1):
            club = row["club_name"]
            if row.get("is_ai"):
                club += " (AI)"
            if not row.get("is_active"):
                club += " 💤"
            club = (club[:17] + "...") if len(club) > 20 else club
            standings_preview += f"{idx:<4} {club:<20} {row['points']:>3}  {row['goal_difference']:+3}\n"
            
        embed.add_field(
            name="📊 Standings (Top 5)",
            value=f"```\n{standings_preview}```",
            inline=False
        )
        
        fixtures_res = await db.table("league_fixtures").select("window_end").eq("season_id", season["id"]).eq("matchday", curr).limit(1).execute()
        window_end_str = ""
        if fixtures_res.data:
            window_end = datetime.fromisoformat(fixtures_res.data[0]["window_end"].replace("Z", "+00:00"))
            window_end_str = f"\n⏳ **Matchday Window Ends**: <t:{int(window_end.timestamp())}:F> (<t:{int(window_end.timestamp())}:R>)"
            
        embed.add_field(
            name="📅 Season Progress",
            value=(
                f"🟢 **Status**: Matchday {curr}/{total} Active\n"
                f"🏆 **Season**: #{season['season_number']}\n"
                f"{window_end_str}"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"ElevenBoss League System • Active Season • Registered Managers: {reg_count}")
        return embed

async def send_league_announcement(guild: discord.Guild, channel_id: int, embed: discord.Embed, message_body: str = "") -> None:
    """
    Sends a league announcement with a split-payload structure:
    Role mentions reside in message content to trigger pings,
    while announcement details reside in embeds for formatting.
    """
    db = await get_client()
    config_res = await db.table("guild_config").select("announcement_role_id").eq("guild_id", guild.id).maybe_single().execute()
    role_id = config_res.data.get("announcement_role_id") if config_res and config_res.data else None
    
    content = ""
    if role_id:
        role = guild.get_role(role_id)
        if role:
            content = f"<@&{role_id}>"
            if message_body:
                content += f"\n\n{message_body}"
        elif message_body:
            content = message_body
    elif message_body:
        content = message_body
        
    channel = guild.get_channel(channel_id)
    if channel:
        await channel.send(content=content if content else None, embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeagueCog(bot))

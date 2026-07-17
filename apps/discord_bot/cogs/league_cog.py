# apps/discord_bot/cogs/league_cog.py
from __future__ import annotations
import logging
import asyncio
import random
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from match_engine import generate_round_robin_fixtures, simulate_match, MatchInput, MatchPlayerCard
from apps.discord_bot.core.locks import get_guild_thread_lock
from apps.discord_bot.core.competitive_display import league_standings_leaderboard_hint
from apps.discord_bot.core.league_journal import (
    get_or_create_league_journal,
    resolve_season_threads,
)
from leagues import compute_form, format_standings_table, sort_standings, tie_breaker_footer

logger = logging.getLogger(__name__)

BOT_NAMES = [
    "Local Pub FC", "Sunday League United", "Park Wanderers", "Metro Athletic",
    "Town Rovers", "Suburban City", "County Rangers", "District FC",
    "State Alliance", "Apex Rovers", "Vanguard City", "Dynamo FC",
    "Zenith United", "Sovereign Athletic", "Majestic FC", "Titan Legends",
    "Antigravity FC", "Grandmasters United"
]

async def _league_join_limits(db) -> tuple[int, int]:
    min_matches, min_days = 10, 7
    try:
        m_res = await db.rpc("get_game_config", {"p_key": "league_join_min_matches"}).execute()
        d_res = await db.rpc("get_game_config", {"p_key": "league_join_min_account_days"}).execute()
        if m_res.data is not None:
            min_matches = int(m_res.data)
        if d_res.data is not None:
            min_days = int(d_res.data)
    except Exception:
        logger.debug("league join limits read failed", exc_info=True)
    return min_matches, min_days


def _account_age_days(created_at) -> int:
    if not created_at:
        return 9999
    if isinstance(created_at, str):
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    else:
        created_dt = created_at
    return (datetime.now(timezone.utc) - created_dt).days


async def _display_entry_fee(db, season: dict | None, division: str = "Grassroots") -> str:
    from economy.flows import EconomyConfig, league_division_tier, league_entry_fee

    base: int | None = None
    if season and season.get("config_json") and "entry_fee_coins" in season["config_json"]:
        base = int(season["config_json"]["entry_fee_coins"])
        if base <= 0:
            return "Free entry"

    c = EconomyConfig()
    if base is not None:
        fee = base + league_division_tier(division) * c.league_entry_fee_per_division
    else:
        fee = league_entry_fee(division, c)
    if fee <= 0:
        return "Free entry"
    return f"**{fee:,}** coins (scales by division; refunded on season complete)"


# --- STANDINGS HELPER ---
async def fetch_standings(
    db, season_id: str, division_tier: int | None = None
) -> list[dict]:
    """
    Fetch aggregated standings for the given season.
    Sort order: Points DESC, Goal Difference DESC, Goals For DESC, Username ASC.
    When ``division_tier`` is set, only participants in that seasonal tier are included.
    """
    parts_res = await db.table("league_participants").select("*, players(*)").eq("season_id", season_id).execute()
    participants = parts_res.data or []
    if division_tier is not None:
        participants = [
            p for p in participants
            if int(p.get("division_tier") or 1) == int(division_tier)
        ]

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
            "division_tier": int(part.get("division_tier") or 1),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "matches_played": matches_played,
            "points": points,
            "goal_difference": gd,
            "form": compute_form(pid, fixtures),
        })

    return sort_standings(standings, fixtures)


async def _award_and_post_momd(
    db,
    season_id: str,
    matchday: int,
    bot: commands.Bot | None = None,
) -> None:
    """Call MoMD RPC for a settled matchday; post Journal on ``awarded``."""
    try:
        res = await db.rpc(
            "award_manager_of_the_matchday",
            {"p_season_id": season_id, "p_matchday": matchday},
        ).execute()
        data = res.data or {}
        if isinstance(data, str):
            import json
            data = json.loads(data)
    except Exception:
        logger.exception("award_manager_of_the_matchday failed season=%s md=%s", season_id, matchday)
        return

    if not data or data.get("status") != "awarded" or not bot:
        return

    try:
        from apps.discord_bot.core.league_journal import post_momd_award, resolve_season_threads

        season_res = await db.table("league_seasons").select("league_id, journal_thread_id, thread_format").eq(
            "id", season_id
        ).maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            return
        league_res = await db.table("leagues").select("guild_id").eq("id", season["league_id"]).maybe_single().execute()
        guild_id = (league_res.data or {}).get("guild_id") if league_res else None
        if not guild_id:
            return
        guild = bot.get_guild(int(guild_id))
        if not guild:
            try:
                guild = await bot.fetch_guild(int(guild_id))
            except Exception:
                return

        threads = await resolve_season_threads(bot, db, guild, season_id)
        journal = threads.journal_thread if threads else None
        if not journal:
            return

        pid = data.get("player_id")
        club_name = f"Club {pid}"
        if pid is not None:
            p_res = await db.table("players").select("club_name").eq("discord_id", int(pid)).maybe_single().execute()
            if p_res and p_res.data:
                club_name = p_res.data.get("club_name") or club_name

        scoreline = "?"
        fixture_id = data.get("fixture_id")
        if fixture_id:
            f_res = await db.table("league_fixtures").select(
                "home_score, away_score"
            ).eq("id", fixture_id).maybe_single().execute()
            if f_res and f_res.data:
                scoreline = f"{f_res.data.get('home_score', 0)}–{f_res.data.get('away_score', 0)}"

        coins = int(data.get("coins") or 2000)
        await post_momd_award(bot, journal, club_name, scoreline, coins)
    except Exception:
        logger.exception("MoMD Journal post failed season=%s md=%s", season_id, matchday)


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

    from apps.discord_bot.core.guild_resolver import (
        pause_season_if_guild_unreachable,
        resolve_bot_guild,
    )

    guild, unreachable = await resolve_bot_guild(bot, guild_id)
    if not guild:
        if unreachable:
            await pause_season_if_guild_unreachable(
                db, season_id, guild_id, "guild_unreachable"
            )
        else:
            season_status_res = await (
                db.table("league_seasons")
                .select("status")
                .eq("id", season_id)
                .maybe_single()
                .execute()
            )
            status = (season_status_res.data or {}).get("status") if season_status_res else None
            if status == "paused":
                logger.debug(
                    "Guild %s transiently unreachable; season %s already paused",
                    guild_id,
                    season_id,
                )
            else:
                logger.warning(
                    "Guild %s temporarily unreachable; skipping auto-sim this run",
                    guild_id,
                )
        return 0
        
    # Resolve threads (dual_v2 or legacy)
    season_threads = await resolve_season_threads(bot, db, guild, season_id)
    if not season_threads:
        logger.warning("Could not resolve league threads for guild %s", guild_id)
        return 0

    from apps.discord_bot.cogs.battle_cog import run_league_match_simulation, LeagueMatchHandler
    from apps.discord_bot.core.match_runs import get_active_fixture_run

    simulated_count = 0
    for f in fixtures:
        window_end_val = f.get("window_end")
        if not window_end_val:
            continue
        window_end = datetime.fromisoformat(window_end_val.replace("Z", "+00:00"))
        if now > window_end:
            if await get_active_fixture_run(db, f["id"]):
                logger.info("Skipping auto-sim for fixture %s — active match run", f["id"])
                continue
            try:
                handler = LeagueMatchHandler(
                    commentary_thread=season_threads.commentary_thread,
                    fixture_id=f["id"],
                    season_id=f["season_id"],
                    journal_thread=season_threads.journal_thread,
                    journal_standings_msg_id=season_threads.journal_standings_message_id,
                )
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
        completed_md = await update_current_matchday(db, season_id, bot=bot)
        if completed_md:
            from apps.discord_bot.core.league_journal import notify_matchday_complete
            await notify_matchday_complete(bot, guild, db, season_id, completed_md)
        
    return simulated_count

async def update_current_matchday(
    db, season_id: str, bot: commands.Bot | None = None
) -> int | None:
    """Advance season matchday when all fixtures in the current week are played.

    Returns the completed matchday number when advanced, else ``None``.
    Awards Manager of the Matchday before advancing (idempotent RPC).
    """
    season_res = await db.table("league_seasons").select("*").eq("id", season_id).maybe_single().execute()
    season = season_res.data if season_res else None
    if not season:
        return None
    curr = season["current_matchday"]
    total = season["total_matchdays"]
    
    unplayed_res = await db.table("league_fixtures").select("id").eq("season_id", season_id).eq("matchday", curr).eq("is_played", False).execute()
    if not unplayed_res.data:
        await _award_and_post_momd(db, season_id, curr, bot=bot)
        if curr < total:
            await db.table("league_seasons").update({"current_matchday": curr + 1}).eq("id", season_id).execute()
            logger.info(f"Season {season_id} advanced to matchday {curr + 1}")
            return curr
        else:
            await db.table("league_seasons").update({
                "status": "completed",
                "end_time": datetime.now(timezone.utc).isoformat()
            }).eq("id", season_id).execute()

            try:
                # RPC pays per-tier prizes and runs seasonal promo/releg for Dynamics
                await db.rpc("distribute_season_prizes", {"p_season_id": season_id}).execute()
                logger.info("Distributed season prizes for %s", season_id)
            except Exception:
                logger.exception("distribute_season_prizes failed for season %s", season_id)
            
            league_res = await db.table("leagues").select("guild_id").eq("id", season["league_id"]).maybe_single().execute()
            if league_res and league_res.data:
                await db.table("guild_config").update({"league_status": "inactive"}).eq("guild_id", league_res.data["guild_id"]).execute()
            logger.info(f"Season {season_id} has been fully completed!")
            return curr
    return None


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

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🔍 Scout Opponent", custom_id="hub_scout_btn", row=1)
    async def scout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.show_opponent_scout(interaction, self)

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
    @app_commands.check(ensure_registered)
    async def league_hub(self, interaction: discord.Interaction) -> None:
        """Slash command to open the Seasonal League Hub."""
        if not interaction.response.is_done():
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
            season_res = await db.table("league_seasons").select("*").eq("league_id", league["id"]).in_(
                "status", ["active", "registration", "paused"]
            ).order("created_at", desc=True).limit(1).maybe_single().execute()
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
            season_res = await db.table("league_seasons").select("*").eq("league_id", league["id"]).in_(
                "status", ["active", "registration", "paused"]
            ).order("created_at", desc=True).limit(1).maybe_single().execute()
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

        fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season["id"]).execute()
        all_fixtures = fixtures_res.data or []

        title = f"📊 League Standings — Season {season['season_number']}"
        dynamics = (season.get("pacing_mode") or "") == "dynamics"
        if dynamics:
            part_res = await (
                db.table("league_participants")
                .select("division_tier")
                .eq("season_id", season["id"])
                .eq("player_id", interaction.user.id)
                .maybe_single()
                .execute()
            )
            viewer_tier = int((part_res.data or {}).get("division_tier") or 1) if part_res else 1
            standings = await fetch_standings(db, season["id"], division_tier=viewer_tier)
            title = f"📊 Seasonal Division {viewer_tier} — Season {season['season_number']}"
        else:
            standings = await fetch_standings(db, season["id"])

        embed = discord.Embed(
            title=title,
            color=0x00FF87
        )
        table_str = format_standings_table(standings, all_fixtures)
        embed.description = f"```\n{table_str}\n```\n*{tie_breaker_footer()}*"
        embed.set_footer(text=league_standings_leaderboard_hint())

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
        dynamics = (season.get("pacing_mode") or "") == "dynamics"

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
                    if dynamics:
                        status_str = f"⏰ Play before 00:00 UTC (Ends <t:{int(window_end.timestamp())}:R>)"
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
        
        # Top Goals (goals > 0)
        filtered_goals = [r for r in stats_rows if r.get("goals", 0) > 0]
        top_goals = sorted(filtered_goals, key=lambda x: x["goals"], reverse=True)[:5]
        goals_lines = []
        for idx, row in enumerate(top_goals, 1):
            manager = row.get("players", {}).get("manager_name") or f"Player {row['player_id']}"
            goals_lines.append(f"**{idx}.** {manager} - {row['goals']} Goals")
        goals_text = "\n".join(goals_lines) if goals_lines else "No goals recorded yet."
        embed.add_field(name="👟 Top Scoring Players (Golden Boot)", value=goals_text, inline=False)

        # Top Assists (assists > 0)
        filtered_assists = [r for r in stats_rows if r.get("assists", 0) > 0]
        top_assists = sorted(filtered_assists, key=lambda x: x["assists"], reverse=True)[:5]
        assists_lines = []
        for idx, row in enumerate(top_assists, 1):
            manager = row.get("players", {}).get("manager_name") or f"Player {row['player_id']}"
            assists_lines.append(f"**{idx}.** {manager} - {row['assists']} Assists")
        assists_text = "\n".join(assists_lines) if assists_lines else "No assists recorded yet."
        embed.add_field(name="🤝 Top Assisting Players", value=assists_text, inline=False)

        # Clean Sheets (clean_sheets > 0)
        filtered_cs = [r for r in stats_rows if r.get("clean_sheets", 0) > 0]
        top_cs = sorted(filtered_cs, key=lambda x: x["clean_sheets"], reverse=True)[:5]
        cs_lines = []
        for idx, row in enumerate(top_cs, 1):
            manager = row.get("players", {}).get("manager_name") or f"Player {row['player_id']}"
            cs_lines.append(f"**{idx}.** {manager} - {row['clean_sheets']} Clean Sheets")
        cs_text = "\n".join(cs_lines) if cs_lines else "No clean sheets recorded yet."
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

        min_matches, min_days = await _league_join_limits(db)
        played = int(player.get("matches_played") or 0)
        if played < min_matches:
            await interaction.followup.send(
                embed=error_embed(
                    f"❌ League registration requires **{min_matches}** career matches "
                    f"(you have **{played}**). Play bot matches first."
                ),
                ephemeral=True,
            )
            return
        age_days = _account_age_days(player.get("created_at"))
        if age_days < min_days:
            await interaction.followup.send(
                embed=error_embed(
                    f"❌ League registration requires a club at least **{min_days}** days old "
                    f"({min_days - age_days} day(s) remaining)."
                ),
                ephemeral=True,
            )
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
        user_id = interaction.user.id
        embed = discord.Embed(
            title=f"🏆 {guild.name} Seasonal League Hub",
            color=0x00FF87
        )

        db = await get_client()
        regs_res = await db.table("league_members").select("player_id", count="exact").eq("guild_id", guild.id).execute()
        reg_count = regs_res.count if regs_res else 0
        max_size = 8
        if season and season.get("config_json"):
            max_size = season["config_json"].get("max_clubs", 8)

        if season and season.get("status") == "registration":
            cfg = season.get("config_json") or {}
            if not isinstance(cfg, dict):
                cfg = {}
            deadline = cfg.get("registration_closes_at") or season.get("end_time")
            deadline_str = ""
            if deadline:
                dt = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
                deadline_str = f"\n⏳ **Registration closes**: <t:{int(dt.timestamp())}:R>"
            min_matches, min_days = await _league_join_limits(db)
            p_res = await db.table("players").select("division").eq("discord_id", user_id).maybe_single().execute()
            division = (p_res.data or {}).get("division", "Grassroots") if p_res else "Grassroots"
            fee_str = await _display_entry_fee(db, season, division)
            if cfg.get("automation"):
                start_note = (
                    "Click **Register** to join.\n"
                    "The season **starts automatically** when registration closes "
                    "(if enough managers have joined)."
                )
                footer = "ElevenBoss League • Automated registration"
            else:
                start_note = "Click **Register** to join the upcoming season roster."
                footer = "ElevenBoss League • Registration phase"
            embed.description = (
                f"📝 **Registration Open** — Season #{season.get('season_number', '?')}\n\n"
                f"Registered: **{reg_count}/{max_size}** managers{deadline_str}\n\n"
                f"💰 Entry fee: {fee_str}\n"
                f"📋 Requires: **{min_matches}** matches played, club **{min_days}**+ days old\n\n"
                f"{start_note}"
            )
            embed.set_footer(text=footer)
            return embed

        if not season:
            embed.description = (
                "Welcome to the Seasonal League Hub!\n\n"
                "💤 **Status**: No active season.\n\n"
                "Click **`[ 📝 Register ]`** to join the roster for the upcoming league season!\n"
                f"Current Registered Managers: **{reg_count}**\n\n"
                "*Server admins can start the season from `/admin` → League Management.*"
            )
            return embed

        if season.get("status") == "paused":
            embed.description = "⏸️ **Season Paused** — matchdays are frozen until an admin resumes."
            return embed

        curr = season["current_matchday"]
        total = season["total_matchdays"]
        dynamics = (season.get("pacing_mode") or "") == "dynamics"

        viewer_tier: int | None = None
        if dynamics:
            part_res = await (
                db.table("league_participants")
                .select("division_tier")
                .eq("season_id", season["id"])
                .eq("player_id", user_id)
                .maybe_single()
                .execute()
            )
            if part_res and part_res.data:
                viewer_tier = int(part_res.data.get("division_tier") or 1)
            else:
                viewer_tier = 1
            standings = await fetch_standings(db, season["id"], division_tier=viewer_tier)
        else:
            standings = await fetch_standings(db, season["id"])

        fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", season["id"]).execute()
        all_fixtures = fixtures_res.data or []

        my_rank = "—"
        my_row = next((r for r in standings if r["discord_id"] == user_id), None)
        if my_row:
            my_rank = str(standings.index(my_row) + 1)

        embed.description = f"🟢 **Matchday {curr}/{total}** — Season #{season['season_number']}"
        if dynamics and viewer_tier is not None:
            embed.description += f"\n📊 **Seasonal Division {viewer_tier}**"

        if my_row:
            embed.add_field(
                name="📍 Your Club",
                value=(
                    f"**{my_row['club_name']}** — #{my_rank}\n"
                    f"Pts: **{my_row['points']}** | GD: **{my_row['goal_difference']:+d}** | Form: `{my_row.get('form', '—')}`"
                ),
                inline=False,
            )

        # Next fixture for user
        user_fixture = None
        for f in all_fixtures:
            if not f.get("is_played") and f.get("matchday") == curr:
                if user_id in (f["home_team_id"], f["away_team_id"]):
                    user_fixture = f
                    break
        if user_fixture:
            opp_id = user_fixture["away_team_id"] if user_fixture["home_team_id"] == user_id else user_fixture["home_team_id"]
            opp_row = next((r for r in standings if r["discord_id"] == opp_id), None)
            opp_name = opp_row["club_name"] if opp_row else "TBD"
            ha = "Home" if user_fixture["home_team_id"] == user_id else "Away"
            embed.add_field(name="⚔️ Next Match", value=f"**{opp_name}** ({ha}) — Matchday {curr}", inline=False)

        table_preview = format_standings_table(standings, all_fixtures, limit=5)
        standings_title = (
            f"📊 Division {viewer_tier} Standings (Top 5)"
            if dynamics and viewer_tier is not None
            else "📊 Standings (Top 5)"
        )
        embed.add_field(name=standings_title, value=f"```\n{table_preview}\n```", inline=False)

        fixtures_md = await db.table("league_fixtures").select("window_end").eq("season_id", season["id"]).eq("matchday", curr).limit(1).execute()
        window_end_str = ""
        if fixtures_md.data:
            window_end = datetime.fromisoformat(fixtures_md.data[0]["window_end"].replace("Z", "+00:00"))
            if dynamics:
                window_end_str = (
                    f"⏰ **Play before 00:00 UTC** — closes <t:{int(window_end.timestamp())}:R>\n"
                )
            else:
                window_end_str = f"⏳ **Window closes**: <t:{int(window_end.timestamp())}:R>\n"

        embed.add_field(
            name="📅 Season Progress",
            value=f"{window_end_str}🏆 Matchday **{curr}** of **{total}**",
            inline=False,
        )
        embed.set_footer(text=f"Registered: {reg_count} • {league_standings_leaderboard_hint()}")
        return embed

    async def show_opponent_scout(self, interaction: discord.Interaction, hub_view: LeagueHubView):
        db = await get_client()
        user_id = interaction.user.id
        league_res = await db.table("leagues").select("id").eq("guild_id", hub_view.guild_id).maybe_single().execute()
        if not league_res or not league_res.data:
            await interaction.edit_original_response(embed=error_embed("No league configured."), view=hub_view)
            return
        season_res = await db.table("league_seasons").select("*").eq("league_id", league_res.data["id"]).eq("status", "active").maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            await interaction.edit_original_response(embed=error_embed("No active season."), view=hub_view)
            return

        curr = season["current_matchday"]
        fix_res = await db.table("league_fixtures").select(
            "*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)"
        ).eq("season_id", season["id"]).eq("matchday", curr).eq("is_played", False).execute()
        my_fix = None
        for f in fix_res.data or []:
            if user_id in (f["home_team_id"], f["away_team_id"]):
                my_fix = f
                break
        if not my_fix:
            await interaction.edit_original_response(embed=error_embed("No upcoming fixture this matchday."), view=hub_view)
            return

        is_home = my_fix["home_team_id"] == user_id
        opp = my_fix["away"] if is_home else my_fix["home"]
        opp_id = my_fix["away_team_id"] if is_home else my_fix["home_team_id"]

        # H2H record
        h2h_res = await db.table("league_fixtures").select("*").eq("season_id", season["id"]).eq("is_played", True).execute()
        h2h_w = h2h_d = h2h_l = 0
        for f in h2h_res.data or []:
            if {f["home_team_id"], f["away_team_id"]} != {user_id, opp_id}:
                continue
            if f["home_score"] == f["away_score"]:
                h2h_d += 1
            elif (f["home_score"] > f["away_score"] and f["home_team_id"] == user_id) or (f["away_score"] > f["home_score"] and f["away_team_id"] == user_id):
                h2h_w += 1
            else:
                h2h_l += 1

        opp_ovr = "AI"
        if not opp.get("is_ai"):
            sa_res = await db.table("squad_assignments").select("player_cards(overall)").eq("discord_id", opp_id).execute()
            ovrs = [a["player_cards"]["overall"] for a in (sa_res.data or []) if a.get("player_cards")]
            opp_ovr = f"{sum(ovrs) / len(ovrs):.1f}" if ovrs else "N/A"

        embed = discord.Embed(
            title=f"🔍 Opponent Scout — {opp.get('club_name', 'Unknown')}",
            description=(
                f"**Manager:** {opp.get('manager_name', 'AI')}\n"
                f"**Avg XI OVR:** {opp_ovr}\n"
                f"**H2H:** {h2h_w}W-{h2h_d}D-{h2h_l}L\n"
                f"**Venue:** {'Home' if is_home else 'Away'}"
            ),
            color=0x3498DB,
        )
        view = StandingsView(self, interaction.user.id, hub_view)
        await interaction.edit_original_response(embed=embed, view=view)

async def send_league_announcement(
    guild: discord.Guild,
    channel_id: int,
    embed: discord.Embed | None = None,
    message_body: str = "",
    *,
    files: list[discord.File] | None = None,
) -> discord.Message | None:
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
    if not channel:
        logger.warning(
            "League announcement channel %s not found in guild %s — message skipped.",
            channel_id,
            guild.id,
        )
        return None
    return await channel.send(
        content=content if content else None,
        embed=embed,
        files=files or [],
        allowed_mentions=discord.AllowedMentions(roles=True),
    )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeagueCog(bot))

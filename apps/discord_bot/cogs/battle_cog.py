# apps/discord_bot/cogs/battle_cog.py
from __future__ import annotations
import logging
import random
import asyncio
import abc
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
from apps.discord_bot.core.locks import get_guild_thread_lock
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def safe_edit_message(message: discord.Message, **kwargs) -> None:
    """Edit with basic 429 backoff for match tickers."""
    for attempt in range(3):
        try:
            await message.edit(**kwargs)
            return
        except discord.HTTPException as e:
            if e.status == 429 and attempt < 2:
                await asyncio.sleep(float(getattr(e, "retry_after", 2) or 2))
            else:
                raise


def _fixture_in_window(fixture: dict) -> bool:
    now = datetime.now(timezone.utc)
    try:
        ws = datetime.fromisoformat(str(fixture["window_start"]).replace("Z", "+00:00"))
        we = datetime.fromisoformat(str(fixture["window_end"]).replace("Z", "+00:00"))
    except (TypeError, ValueError, KeyError):
        return True
    return ws <= now <= we

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

class ChallengeView(discord.ui.View):
    def __init__(self, cog: BattleCog, challenger: discord.Member | discord.User, opponent: discord.Member, original_interaction: discord.Interaction) -> None:
        super().__init__(timeout=60.0)
        self.cog = cog
        self.challenger = challenger
        self.opponent = opponent
        self.original_interaction = original_interaction
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("❌ This challenge belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.success, label="✅ Accept", custom_id="challenge_accept")
    async def accept_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(
            content=f"🤝 Challenge accepted by {self.opponent.mention}! Match is preparing...",
            view=None
        )
        
        asyncio.create_task(
            self.cog.start_friendly_match(
                interaction=interaction,
                challenger=self.challenger,
                opponent=self.opponent,
                invitation_msg=interaction.message
            )
        )

    @discord.ui.button(style=discord.ButtonStyle.danger, label="❌ Decline", custom_id="challenge_decline")
    async def decline_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(
            content=f"❌ The challenge was declined by **{self.opponent.display_name}**.",
            view=None
        )

    async def on_timeout(self) -> None:
        self.stop()
        if self.message:
            try:
                await self.message.edit(
                    content=f"⏳ The challenge from **{self.challenger.display_name}** to **{self.opponent.display_name}** has timed out.",
                    view=None
                )
            except Exception:
                pass

class IMatchOutputHandler(abc.ABC):
    @abc.abstractmethod
    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None) -> discord.abc.Messageable:
        """Post initial ticket, optional thread, and return the target channel/thread for posting commentary."""
        pass

    @abc.abstractmethod
    async def start_match(self, target: discord.abc.Messageable, home_name: str, away_name: str, touchline_view: discord.ui.View | None) -> None:
        """Send the initial match scoreboard/momentum/commentary state."""
        pass

    @abc.abstractmethod
    async def update_ticker(self, ev: dict, state: MatchState, recent_ticker: list[str], touchline_view: discord.ui.View | None) -> None:
        """Update the match scoreboard/momentum/commentary state for a match tick."""
        pass

    @abc.abstractmethod
    async def finalize_match(self, result: MatchResult, state: MatchState, home_name: str, away_name: str, motm: str, active_earned: int, active_pts: int, user_id: int, home_team_id: int, away_team_id: int, **kwargs) -> None:
        """Send post-match press conference, pings, and handle thread renaming/archival."""
        pass

class StandardMatchHandler(IMatchOutputHandler):
    def __init__(self, bot: commands.Bot, league_mode: bool = False) -> None:
        self.bot = bot
        self.league_mode = league_mode
        self.ticket_msg = None
        self.thread = None
        self.ticker_msg = None

    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None) -> discord.abc.Messageable:
        if not interaction:
            raise ValueError("StandardMatchHandler requires an active interaction context.")

        ticket_embed = discord.Embed(
            title=f"🎫 Match Ticket: {home_name} vs {away_name}",
            description="A new match has kicked off! Live commentary is streaming now.",
            color=0x00FF87
        )
        if matchday:
            ticket_embed.add_field(name="Matchday", value=f"Matchday {matchday}", inline=True)
        ticket_embed.add_field(name="Cost", value="⚡ 10 Energy", inline=True)

        if interaction.response.is_done():
            self.ticket_msg = await interaction.channel.send(embed=ticket_embed)
        else:
            self.ticket_msg = await interaction.followup.send(embed=ticket_embed)

        self.thread = None
        if not self.league_mode and interaction.guild and hasattr(interaction.channel, "create_thread"):
            try:
                self.thread = await interaction.channel.create_thread(
                    name=f"🏟️ {home_name} vs {away_name} - Live",
                    message=self.ticket_msg,
                    auto_archive_duration=60
                )
            except Exception as e:
                logger.warning(f"Failed to create public match thread: {e}. Falling back to main channel.")

        if self.thread:
            ticket_embed.add_field(name="Stadium Thread", value=self.thread.mention, inline=False)
            await self.ticket_msg.edit(embed=ticket_embed)

        return self.thread if self.thread else interaction.channel

    async def start_match(self, target: discord.abc.Messageable, home_name: str, away_name: str, touchline_view: discord.ui.View | None) -> None:
        self.home_name = home_name
        self.away_name = away_name
        init_embed = discord.Embed(
            title=f"🏟️ Live Stadium: {home_name} vs {away_name}",
            color=0x00FF87
        )
        init_embed.add_field(name="Scoreboard", value=f"🏟️ **{home_name}** `0 - 0` **{away_name}**", inline=False)
        init_embed.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
        init_embed.add_field(name="Commentary Ticker", value="🟢 **0'** - The referee blows the whistle and we are underway!", inline=False)

        self.ticker_msg = await target.send(embed=init_embed, view=touchline_view)

    async def update_ticker(self, ev: dict, state: MatchState, recent_ticker: list[str], touchline_view: discord.ui.View | None) -> None:
        embed = discord.Embed(
            title=f"🏟️ Live Stadium: {self.home_name or 'Home'} vs {self.away_name or 'Away'}",
            color=0x00FF87
        )
        embed.add_field(name="Scoreboard", value=f"🏟️ **{self.home_name or 'Home'}** `{ev['score_update']}` **{self.away_name or 'Away'}**", inline=False)
        embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
        embed.add_field(name="Commentary Ticker", value="\n".join(recent_ticker), inline=False)

        await safe_edit_message(self.ticker_msg, embed=embed, view=touchline_view)

    async def finalize_match(self, result: MatchResult, state: MatchState, home_name: str, away_name: str, motm: str, active_earned: int, active_pts: int, user_id: int, home_team_id: int, away_team_id: int, **kwargs) -> None:
        target = self.thread if self.thread else self.ticker_msg.channel
        press_embed = discord.Embed(
            title="🎙️ Post-Match Press Conference",
            description="Reporters gather as the managers discuss the game statistics and performance.",
            color=0xFFCC00
        )
        result_emoji = "🎉 WIN" if result.result == "win" else ("🤝 DRAW" if result.result == "draw" else "💔 LOSS")
        
        press_embed.add_field(
            name="🥅 Final Result",
            value=f"### {result_emoji}\n**{home_name}** `{result.goals_for} - {result.goals_against}` **{away_name}**",
            inline=False
        )
        press_embed.add_field(
            name="📊 Match Statistics",
            value=(
                f"**Possession**: {result.possession_home}% - {result.possession_away}%\n"
                f"**Shots**: {result.shots_home} - {result.shots_away}\n"
                f"**Man of the Match**: ⭐ **{motm}**"
            ),
            inline=True
        )
        
        lp_change = kwargs.get("lp_change")
        total_lp = kwargs.get("total_lp")
        division_name = kwargs.get("division_name")
        
        rewards_lines = [f"🪙 **+{active_earned} coins**"]
        if lp_change is not None:
            sign = "+" if lp_change >= 0 else ""
            rewards_lines.append(f"🏆 **{sign}{lp_change} LP** (Total: {total_lp} LP - {division_name})")
        else:
            rewards_lines.append(f"🏆 **+{active_pts} league pts**")

        press_embed.add_field(
            name="🎁 Rewards",
            value="\n".join(rewards_lines),
            inline=True
        )
        press_embed.set_footer(text="✅ Rewards, XP gains, and league standings saved to database.")
        await target.send(embed=press_embed)

        if self.thread:
            try:
                await self.thread.edit(name=f"🏆 {home_name} {result.goals_for}-{result.goals_against} {away_name}")
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

            asyncio.create_task(archive_thread_after_delay(self.thread, 180.0))

class LeagueMatchHandler(IMatchOutputHandler):
    def __init__(self, output_thread: discord.Thread, fixture_id: str = None, season_id: str = None) -> None:
        self.output_thread = output_thread
        self.fixture_id = fixture_id
        self.season_id = season_id
        self.ticker_msg = None

    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None) -> discord.abc.Messageable:
        return self.output_thread

    async def start_match(self, target: discord.abc.Messageable, home_name: str, away_name: str, touchline_view: discord.ui.View | None) -> None:
        self.home_name = home_name
        self.away_name = away_name
        init_embed = discord.Embed(
            title=f"🏟️ Live League Match: {home_name} vs {away_name}",
            color=0x00FF87
        )
        init_embed.add_field(name="Scoreboard", value=f"🏟️ **{home_name}** `0 - 0` **{away_name}**", inline=False)
        init_embed.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
        init_embed.add_field(name="Live Commentary", value="🟢 **0'** - The referee blows the whistle and we are underway!", inline=False)

        self.ticker_msg = await target.send(embed=init_embed, view=touchline_view)

    async def update_ticker(self, ev: dict, state: MatchState, recent_ticker: list[str], touchline_view: discord.ui.View | None) -> None:
        embed = discord.Embed(
            title=f"🏟️ Live League Match: {self.home_name or 'Home'} vs {self.away_name or 'Away'}",
            color=0x00FF87
        )
        embed.add_field(name="Scoreboard", value=f"🏟️ **{self.home_name or 'Home'}** `{ev['score_update']}` **{self.away_name or 'Away'}**", inline=False)
        embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
        embed.add_field(name="Live Commentary", value="\n".join(recent_ticker), inline=False)

        await safe_edit_message(self.ticker_msg, embed=embed, view=touchline_view)

    async def finalize_match(self, result: MatchResult, state: MatchState, home_name: str, away_name: str, motm: str, active_earned: int, active_pts: int, user_id: int, home_team_id: int, away_team_id: int, **kwargs) -> None:
        if self.ticker_msg:
            try:
                finished_embed = discord.Embed(
                    title=f"🏁 League Match Finished: {home_name} `{state.home_score} - {state.away_score}` {away_name}",
                    color=0x888888
                )
                finished_embed.add_field(name="Scoreboard", value=f"🏁 **{home_name}** `{state.home_score} - {state.away_score}` **{away_name}**", inline=False)
                finished_embed.add_field(name="📈 Final Momentum", value=get_momentum_bar(state.momentum), inline=False)
                await safe_edit_message(self.ticker_msg, embed=finished_embed, view=None)
            except Exception:
                pass

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
        press_embed.add_field(
            name="📊 Match Statistics",
            value=(
                f"**Possession**: {result.possession_home}% - {result.possession_away}%\n"
                f"**Shots**: {result.shots_home} - {result.shots_away}\n"
                f"**Man of the Match**: ⭐ **{motm}**"
            ),
            inline=True
        )

        rewards_text = ""
        db = await get_client()
        # Find home manager info
        home_res = await db.table("players").select("*").eq("discord_id", home_team_id).maybe_single().execute()
        home_p = home_res.data if home_res else None
        # Find away manager info
        away_res = await db.table("players").select("*").eq("discord_id", away_team_id).maybe_single().execute()
        away_p = away_res.data if away_res else None

        if home_p and not home_p["is_ai"]:
            home_result_str = "win" if state.home_score > state.away_score else ("draw" if state.home_score == state.away_score else "loss")
            home_coins = 150 if home_result_str == "win" else (50 if home_result_str == "draw" else 0)
            home_pts = 3 if home_result_str == "win" else (1 if home_result_str == "draw" else 0)
            rewards_text += f"🏡 **{home_name}**: `🪙 +{home_coins} coins`, `🏆 +{home_pts} pts`\n"
        if away_p and not away_p["is_ai"]:
            away_result_str = "win" if state.away_score > state.home_score else ("draw" if state.away_score == state.home_score else "loss")
            away_coins = 150 if away_result_str == "win" else (50 if away_result_str == "draw" else 0)
            away_pts = 3 if away_result_str == "win" else (1 if away_result_str == "draw" else 0)
            rewards_text += f"✈️ **{away_name}**: `🪙 +{away_coins} coins`, `🏆 +{away_pts} pts`\n"

        if rewards_text:
            press_embed.add_field(name="🎁 Match Rewards", value=rewards_text, inline=True)
        
        press_embed.set_footer(text="✅ Rewards, XP gains, and league standings saved to database.")

        winner_name = home_name if state.home_score > state.away_score else (away_name if state.away_score > state.home_score else None)
        congrat_ping = ""
        pings = []
        if home_p and not home_p["is_ai"]:
            pings.append(f"<@{home_team_id}>")
        if away_p and not away_p["is_ai"]:
            pings.append(f"<@{away_team_id}>")

        if pings:
            ping_str = " and ".join(pings)
            if winner_name:
                congrat_ping = f"{ping_str} - Congratulations to **{winner_name}** on a hard-fought victory!"
            else:
                congrat_ping = f"{ping_str} - A hard-fought draw!"

        await self.output_thread.send(content=congrat_ping if congrat_ping else None, embed=press_embed)

        # 1. Write to match_logs
        if self.fixture_id:
            try:
                box_score = {
                    "home_goals": state.home_score,
                    "away_goals": state.away_score,
                    "possession_home": result.possession_home,
                    "possession_away": result.possession_away,
                    "shots_home": result.shots_home,
                    "shots_away": result.shots_away,
                    "motm": motm
                }
                await db.table("match_logs").upsert({
                    "fixture_id": self.fixture_id,
                    "box_score": box_score,
                    "key_events": result.key_events
                }).execute()
                logger.info(f"[Trace] [finalize_match] Wrote match log for fixture {self.fixture_id}")
            except Exception as le:
                logger.error(f"Failed to write match logs: {le}", exc_info=True)

        # 2. Write to player_season_stats (Human managers only)
        if self.season_id:
            try:
                h_id = int(home_team_id)
                a_id = int(away_team_id)
                manager_ids = []
                if home_p and not home_p["is_ai"]:
                    manager_ids.append(h_id)
                if away_p and not away_p["is_ai"]:
                    manager_ids.append(a_id)

                if manager_ids:
                    # Resolve MOTM owner
                    is_home_motm = False
                    is_away_motm = False
                    try:
                        assignments_res = await db.table("squad_assignments").select("discord_id, player_cards(name)").in_("discord_id", manager_ids).execute()
                        if assignments_res.data:
                            for assign in assignments_res.data:
                                card = assign.get("player_cards")
                                if card and card.get("name") == motm:
                                    if assign["discord_id"] == h_id:
                                        is_home_motm = True
                                    elif assign["discord_id"] == a_id:
                                        is_away_motm = True
                                    break
                    except Exception as s_err:
                        logger.warning(f"Could not resolve MOTM owner: {s_err}")

                    existing_res = await db.table("player_season_stats").select("*").eq("season_id", self.season_id).in_("player_id", manager_ids).execute()
                    existing_data = {r["player_id"]: r for r in (existing_res.data or [])}

                    stats_to_upsert = []

                    if home_p and not home_p["is_ai"]:
                        old = existing_data.get(h_id, {
                            "goals": 0, "assists": 0, "clean_sheets": 0, "motm_awards": 0, "matches_played": 0, "average_rating": 6.00
                        })
                        new_goals = old["goals"] + state.home_score
                        home_assists = sum(1 for ev in result.key_events if ev.get("type") == "GOAL" and ev.get("team") == home_name and "assister" in ev)
                        new_assists = old["assists"] + home_assists
                        is_cs = 1 if state.away_score == 0 else 0
                        new_cs = old["clean_sheets"] + is_cs
                        new_motm = old["motm_awards"] + (1 if is_home_motm else 0)
                        new_matches = old["matches_played"] + 1
                        
                        match_rating = max(4.0, min(10.0, 6.0 + (state.home_score * 0.8) + (1.0 if is_cs else 0) - (state.away_score * 0.5)))
                        new_rating = round(((float(old["average_rating"]) * old["matches_played"]) + match_rating) / new_matches, 2)

                        stats_to_upsert.append({
                            "player_id": h_id,
                            "season_id": self.season_id,
                            "goals": new_goals,
                            "assists": new_assists,
                            "clean_sheets": new_cs,
                            "motm_awards": new_motm,
                            "matches_played": new_matches,
                            "average_rating": new_rating
                        })

                    if away_p and not away_p["is_ai"]:
                        old = existing_data.get(a_id, {
                            "goals": 0, "assists": 0, "clean_sheets": 0, "motm_awards": 0, "matches_played": 0, "average_rating": 6.00
                        })
                        new_goals = old["goals"] + state.away_score
                        away_assists = sum(1 for ev in result.key_events if ev.get("type") == "GOAL" and ev.get("team") == away_name and "assister" in ev)
                        new_assists = old["assists"] + away_assists
                        is_cs = 1 if state.home_score == 0 else 0
                        new_cs = old["clean_sheets"] + is_cs
                        new_motm = old["motm_awards"] + (1 if is_away_motm else 0)
                        new_matches = old["matches_played"] + 1
                        
                        match_rating = max(4.0, min(10.0, 6.0 + (state.away_score * 0.8) + (1.0 if is_cs else 0) - (state.home_score * 0.5)))
                        new_rating = round(((float(old["average_rating"]) * old["matches_played"]) + match_rating) / new_matches, 2)

                        stats_to_upsert.append({
                            "player_id": a_id,
                            "season_id": self.season_id,
                            "goals": new_goals,
                            "assists": new_assists,
                            "clean_sheets": new_cs,
                            "motm_awards": new_motm,
                            "matches_played": new_matches,
                            "average_rating": new_rating
                        })

                    if stats_to_upsert:
                        print(f"[Trace] Upserting player stats: {stats_to_upsert}")
                        await db.table("player_season_stats").upsert(stats_to_upsert).execute()
                        logger.info(f"[Trace] [finalize_match] Upserted player_season_stats for season {self.season_id}")
            except Exception as se:
                logger.error(f"Failed to update player season stats: {se}", exc_info=True)

async def run_league_match_simulation(
    bot: commands.Bot,
    db,
    guild: discord.Guild,
    fixture: dict,
    active_player_id: int | None,
    handler: IMatchOutputHandler
) -> None:
    home_p = fixture["home"]
    away_p = fixture["away"]
    fixture_id = fixture["id"]
    
    # ponytail: energy deducted after successful sim (see end of function)
    
    # Load squads & ratings
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
        assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", fixture["home_team_id"]).execute()
        assignments = assignments_res.data or []
        home_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
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
        if len(home_squad) > 0:
            home_rating = sum(p.overall for p in home_squad) / len(home_squad)
        
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
        assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", fixture["away_team_id"]).execute()
        assignments = assignments_res.data or []
        away_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
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
        if len(away_squad) > 0:
            away_rating = sum(p.overall for p in away_squad) / len(away_squad)

    state = MatchState(home_rating=home_rating, away_rating=away_rating)
    commentary_engine = CommentaryEngine()
    
    home_name = home_p["club_name"] + (" (AI)" if home_p["is_ai"] else "")
    away_name = away_p["club_name"] + (" (AI)" if away_p["is_ai"] else "")

    target = await handler.initialize(None, home_name, away_name, fixture["matchday"])
    
    touchline_user_id = active_player_id if active_player_id else 0
    touchline_view = TouchlineView(state, touchline_user_id) if touchline_user_id else None
    
    await handler.start_match(target, home_name, away_name, touchline_view)

    ticker_history: list[str] = []
    key_events_list: list[dict] = []
    async for ev in stream_match(state, home_squad, away_squad, home_name, away_name):
        variables = {"actor": ev["actor"], "team": ev["team"]}
        comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
        text = comm["text"]
        urgency = comm["urgency"]
        
        emoji_map = {
            "KICKOFF": "🟢", "HALF_TIME": "⏸️", "GOAL": "⚽", "MISS": "❌",
            "CHANCE": "🎯", "FOUL": "💥", "YELLOW_CARD": "🟨",
            "INJURY": "🩹", "FULL_TIME": "🏁"
        }
        emo = emoji_map.get(ev["type"], "⏱️")
        
        ticker_history.append(f"{emo} **{ev['minute']}'** - {text}")
        recent_ticker = ticker_history[-5:]
        
        # Accumulate key events
        if ev["type"] in ["KICKOFF", "HALF_TIME", "GOAL", "YELLOW_CARD", "INJURY", "FULL_TIME"]:
            event_entry = {
                "minute": ev["minute"],
                "type": ev["type"],
                "actor": ev["actor"],
                "team": ev["team"],
                "text": text
            }
            if "assister" in ev:
                event_entry["assister"] = ev["assister"]
            key_events_list.append(event_entry)
            
        await handler.update_ticker(ev, state, recent_ticker, touchline_view)
        
        if ev["type"] in ["FULL_TIME", "HALF_TIME"]:
            sleep_time = 2.0
        elif urgency == "cliffhanger":
            sleep_time = 2.0
        elif urgency == "build_up":
            sleep_time = 1.5
        else:
            sleep_time = 1.0
            
        await asyncio.sleep(sleep_time)

    if touchline_view:
        for child in touchline_view.children:
            child.disabled = True

    if active_player_id:
        ap_res = await db.table("players").select("energy").eq("discord_id", active_player_id).maybe_single().execute()
        if ap_res and ap_res.data and ap_res.data["energy"] >= 10:
            await db.table("players").update({
                "energy": ap_res.data["energy"] - 10
            }).eq("discord_id", active_player_id).execute()

    await db.table("league_fixtures").update({
        "home_score": state.home_score,
        "away_score": state.away_score,
        "is_played": True,
        "played_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", fixture_id).execute()

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
        }).eq("discord_id", fixture["home_team_id"]).execute()
        await db.table("match_history").insert({
            "player_id": fixture["home_team_id"], "result": home_result_str, "my_rating": home_rating,
            "opponent_rating": away_rating, "goals_for": state.home_score, "goals_against": state.away_score,
            "coins_earned": home_coins, "points_earned": home_pts
        }).execute()
        c_ids = [c["id"] for c in home_cards]
        await db.rpc("process_match_result", {"p_result": home_result_str, "p_card_ids": c_ids, "p_xp_amount": 15}).execute()
        
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
        }).eq("discord_id", fixture["away_team_id"]).execute()
        await db.table("match_history").insert({
            "player_id": fixture["away_team_id"], "result": away_result_str, "my_rating": away_rating,
            "opponent_rating": home_rating, "goals_for": state.away_score, "goals_against": state.home_score,
            "coins_earned": away_coins, "points_earned": away_pts
        }).execute()
        c_ids = [c["id"] for c in away_cards]
        await db.rpc("process_match_result", {"p_result": away_result_str, "p_card_ids": c_ids, "p_xp_amount": 15}).execute()

    all_human_cards = home_squad if not home_p["is_ai"] else (away_squad if not away_p["is_ai"] else [])
    motm = random.choice(all_human_cards).name if all_human_cards else "AI Match MVP"

    match_res = MatchResult(
        result="win" if state.home_score != state.away_score else "draw",
        goals_for=state.home_score,
        goals_against=state.away_score,
        my_rating=home_rating,
        opponent_rating=away_rating,
        possession_home=state.home_score * 3 + 45,
        possession_away=100 - (state.home_score * 3 + 45),
        shots_home=state.home_score + random.randint(3, 8),
        shots_away=state.away_score + random.randint(3, 8),
        motm=motm,
        coins_earned=home_coins if active_player_id == fixture["home_team_id"] else away_coins,
        points_earned=home_pts if active_player_id == fixture["home_team_id"] else away_pts,
        key_events=key_events_list
    )

    active_earned = home_coins if active_player_id == fixture["home_team_id"] else away_coins
    active_pts = home_pts if active_player_id == fixture["home_team_id"] else away_pts
    
    await handler.finalize_match(
        result=match_res,
        state=state,
        home_name=home_name,
        away_name=away_name,
        motm=motm,
        active_earned=active_earned,
        active_pts=active_pts,
        user_id=active_player_id or 0,
        home_team_id=fixture["home_team_id"],
        away_team_id=fixture["away_team_id"]
    )

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

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🤝 Friendly Match", custom_id="arena_friendly")
    async def friendly_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🤝 **Friendly Match**: To challenge another manager, use the `/battle friendly` slash command (e.g. `/battle friendly opponent:@Manager`).",
            ephemeral=True
        )

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
    async def bot_battle_command(self, interaction: discord.Interaction) -> None:
        await self.execute_bot_battle(interaction)

    @battle_group.command(name="friendly", description="Challenge another manager to a live friendly match.")
    @app_commands.describe(opponent="The manager you want to challenge.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def friendly_match_command(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        challenger = interaction.user
        if challenger.id == opponent.id:
            await interaction.followup.send(embed=error_embed("You cannot challenge yourself!"), ephemeral=True)
            return

        db = await get_client()

        # Check if opponent is registered
        opp_res = await db.table("players").select("*").eq("discord_id", opponent.id).maybe_single().execute()
        opp_player = opp_res.data if opp_res else None
        if not opp_player:
            await interaction.followup.send(embed=error_embed(f"The manager {opponent.display_name} is not registered yet!"), ephemeral=True)
            return

        # Check if either player is already locked in match_locks
        locks_res = await db.table("match_locks").select("*").in_("discord_id", [challenger.id, opponent.id]).execute()
        active_locks = locks_res.data or []
        if active_locks:
            locked_ids = [l["discord_id"] for l in active_locks]
            if challenger.id in locked_ids and opponent.id in locked_ids:
                msg = "Both you and the opponent are currently locked in another match."
            elif challenger.id in locked_ids:
                msg = "You are currently locked in another match."
            else:
                msg = f"{opponent.display_name} is currently locked in another match."
            await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
            return

        # Issue challenge
        await interaction.followup.send(embed=success_embed(f"Challenge issued to {opponent.mention}!"), ephemeral=True)

        view = ChallengeView(self, challenger, opponent, interaction)
        challenge_msg = await interaction.channel.send(
            content=f"⚔️ {opponent.mention}, you have been challenged to a Friendly Match by **{challenger.display_name}**!",
            view=view
        )
        view.message = challenge_msg
    async def execute_bot_battle(self, interaction: discord.Interaction) -> None:
        lock_acquired = False
        try:
            db = await get_client()

            # Concurrency Lock Check
            locks_res = await db.table("match_locks").select("*").eq("discord_id", interaction.user.id).execute()
            if locks_res.data:
                await interaction.followup.send(embed=error_embed("You are currently locked in another match."), ephemeral=True)
                return

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

            # Acquire lock
            await db.table("match_locks").insert({"discord_id": interaction.user.id, "lock_type": "bot"}).execute()
            lock_acquired = True

            # 3. Fetch starting 11 details
            assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", interaction.user.id).execute()
            assignments = assignments_res.data or []
            active_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
            count = len(active_cards)
 
            if count != 11:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Your starting squad must have exactly **11 players** assigned to play a match (current: **{count}/11**).\n"
                        "Configure your starting 11 using `/squad` first."
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
                        def_stat=c.get("def", 50),
                        phy=c.get("phy", 50),
                        morale=c.get("morale", 80),
                        playstyles=playstyles
                    )
                )
 
            # Fetch global divisions
            div_res = await db.table("global_divisions").select("*").order("min_lp", desc=True).execute()
            divisions = div_res.data or []

            user_lp = player.get("global_lp", 0)
            current_div = None
            for div in divisions:
                if user_lp >= div["min_lp"]:
                    current_div = div
                    break
            
            if not current_div:
                current_div = {"name": "Bronze III", "bot_ovr_min": 50, "bot_ovr_max": 60, "win_coins": 100}

            div_name_base = current_div["name"].split()[0]  # e.g., Bronze, Silver, Gold, Elite
            mapping = {
                "Bronze": "Grassroots",
                "Silver": "Semi-Pro",
                "Gold": "Professional",
                "Elite": "Elite"
            }
            mapped_key = mapping.get(div_name_base, "Grassroots")
            opp_name = random.choice(OPPONENT_NAMES.get(mapped_key, ["AI Club"]))
            
            bot_min = current_div["bot_ovr_min"]
            bot_max = current_div["bot_ovr_max"]
            opp_rating = float(random.randint(bot_min, bot_max))

            # Compute manager team base rating
            my_rating = sum(p.overall for p in match_cards) / len(match_cards)

            # 5. Instantiate V2 MatchState and CommentaryEngine
            state = MatchState(home_rating=my_rating, away_rating=opp_rating)
            commentary_engine = CommentaryEngine()

            # Instantiate StandardMatchHandler
            handler = StandardMatchHandler(self.bot, league_mode=False)

            # Initialize target channel
            target = await handler.initialize(interaction, player["club_name"], opp_name)

            touchline_view = TouchlineView(state, interaction.user.id)
            await handler.start_match(target, player["club_name"], opp_name, touchline_view)

            opp_squad = [
                MatchPlayerCard(name="Opponent Striker", position="FWD", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Midfielder", position="MID", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Defender", position="DEF", overall=int(opp_rating)),
            ]

            # Commentary Streaming Loop
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
                    "HALF_TIME": "⏸️",
                    "GOAL": "⚽",
                    "MISS": "❌",
                    "CHANCE": "🎯",
                    "FOUL": "🟨",
                    "FULL_TIME": "🏁"
                }
                emo = emoji_map.get(ev["type"], "⏱️")

                ticker_history.append(f"{emo} **{ev['minute']}'** - {text}")
                recent_ticker = ticker_history[-5:]

                await handler.update_ticker(ev, state, recent_ticker, touchline_view)

                if ev["type"] in ["FULL_TIME", "HALF_TIME"]:
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
            
            # Generate MatchResult and rewards
            win_coins = current_div["win_coins"]
            if state.home_score > state.away_score:
                res_str = "win"
                coins_earned = win_coins
                points_earned = 3
                lp_change = 15
            elif state.home_score == state.away_score:
                res_str = "draw"
                coins_earned = win_coins // 3
                points_earned = 1
                lp_change = 5
            else:
                res_str = "loss"
                coins_earned = 15  # consolation
                points_earned = 0
                lp_change = -10

            new_lp = max(0, user_lp + lp_change)
            actual_lp_change = new_lp - user_lp

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

            # Transaction Safety Payouts
            new_energy = player["energy"] - 10
            new_coins = player["coins"] + result.coins_earned
            new_points = player["league_points"] + result.points_earned
            new_gd = player["goal_difference"] + (result.goals_for - result.goals_against)
            new_matches_played = player["matches_played"] + 1

            new_wins = player["wins"] + (1 if result.result == "win" else 0)
            new_draws = player["draws"] + (1 if result.result == "draw" else 0)
            new_losses = player["losses"] + (1 if result.result == "loss" else 0)

            # Write standings updates (including global_lp)
            await db.table("players").update({
                "energy": new_energy,
                "coins": new_coins,
                "league_points": new_points,
                "global_lp": new_lp,
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

            # Match new division for displaying in press conference
            new_div_name = "Bronze III"
            for div in divisions:
                if new_lp >= div["min_lp"]:
                    new_div_name = div["name"]
                    break

            await handler.finalize_match(
                result=result,
                state=state,
                home_name=player["club_name"],
                away_name=opp_name,
                motm=result.motm,
                active_earned=result.coins_earned,
                active_pts=result.points_earned,
                user_id=interaction.user.id,
                home_team_id=interaction.user.id,
                away_team_id=0
            )
        except Exception as e:
            logger.exception("Failed to simulate match.")
            if interaction.response.is_done():
                await interaction.channel.send(embed=error_embed(f"An error occurred: {str(e)}"))
            else:
                await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)
        finally:
            if lock_acquired:
                await db.table("match_locks").delete().eq("discord_id", interaction.user.id).execute()

    async def execute_league_match(self, interaction: discord.Interaction, fixture: dict) -> None:
        lock_acquired = False
        try:
            db = await get_client()
            user_id = interaction.user.id

            # Concurrency Lock Check
            locks_res = await db.table("match_locks").select("*").eq("discord_id", user_id).execute()
            if locks_res.data:
                await interaction.followup.send(embed=error_embed("You are currently locked in another match."), ephemeral=True)
                return

            # Acquire lock
            await db.table("match_locks").insert({"discord_id": user_id, "lock_type": "league"}).execute()
            lock_acquired = True

            fixture_id = fixture["id"]
            
            # Re-fetch fixture to make sure it's not already played
            f_res = await db.table("league_fixtures").select("*, home:players!league_fixtures_home_team_id_fkey(*), away:players!league_fixtures_away_team_id_fkey(*)").eq("id", fixture_id).maybe_single().execute()
            f = f_res.data if f_res else None
            if not f:
                await interaction.followup.send(embed=error_embed("Fixture not found."), ephemeral=True)
                return
                
            if f["is_played"]:
                await interaction.followup.send(embed=error_embed("This fixture has already been played."), ephemeral=True)
                return

            if not _fixture_in_window(f):
                await interaction.followup.send(
                    embed=error_embed("This fixture is outside its play window."),
                    ephemeral=True,
                )
                return
                
            # Verify user is home or away team manager
            if user_id not in [f["home_team_id"], f["away_team_id"]]:
                await interaction.followup.send(embed=error_embed("You are not a manager in this fixture."), ephemeral=True)
                return
                
            # Fetch active player metadata (the one who triggered the match)
            active_p_res = await db.table("players").select("*").eq("discord_id", user_id).maybe_single().execute()
            active_p = active_p_res.data if active_p_res else None
            if not active_p:
                await interaction.followup.send(embed=error_embed("Active player profile not found."), ephemeral=True)
                return
                
            if active_p["energy"] < 10:
                await interaction.followup.send(
                    embed=error_embed(f"Insufficient energy. Matches require **10 energy**, but you only have **{active_p['energy']}**."),
                    ephemeral=True
                )
                return
                
            # Resolve thread (with concurrency lock)
            guild_id = interaction.guild_id
            logger.info(f"[Trace] [execute_league_match] Match start requested for guild {guild_id} by user {user_id}. Requesting lock...")
            
            lock = await get_guild_thread_lock(guild_id)
            async with lock:
                logger.info(f"[Trace] [execute_league_match] Lock acquired for guild {guild_id}.")
                config_res = await db.table("guild_config").select("*").eq("guild_id", guild_id).maybe_single().execute()
                config = config_res.data if config_res else None
                
                league_channel_id = config.get("league_channel_id") if config else None
                league_updates_thread_id = config.get("league_updates_thread_id") if config else None
                
                logger.info(f"[Trace] [execute_league_match] DB thread check: league_updates_thread_id={league_updates_thread_id}")

                if not league_channel_id:
                    await interaction.followup.send(embed=error_embed("League announcement channel is not configured by the admin."), ephemeral=True)
                    return
                    
                announcement_channel = interaction.guild.get_channel(league_channel_id)
                if not announcement_channel:
                    await interaction.followup.send(embed=error_embed("League announcement channel not found or inaccessible."), ephemeral=True)
                    return

                thread = None
                if league_updates_thread_id:
                    thread = interaction.guild.get_thread(league_updates_thread_id)
                    logger.info(f"[Trace] [execute_league_match] Cache check for thread {league_updates_thread_id}: thread_found={thread is not None}")
                    if not thread:
                        try:
                            thread = await interaction.guild.fetch_channel(league_updates_thread_id)
                            logger.info(f"[Trace] [execute_league_match] API fetch check for thread {league_updates_thread_id}: thread_found={thread is not None}")
                        except discord.NotFound:
                            logger.warning(f"[Trace] [execute_league_match] API fetch failed: thread {league_updates_thread_id} NotFound.")
                            thread = None
                        except Exception as e:
                            logger.error(f"[Trace] [execute_league_match] API fetch failed with error: {e}")
                            thread = None

                if not thread:
                    logger.info(f"[Trace] [execute_league_match] Thread is missing or invalid. Initiating thread creation in channel {league_channel_id}...")
                    try:
                        thread = await announcement_channel.create_thread(
                            name="📰 league-journal",
                            type=discord.ChannelType.public_thread,
                            auto_archive_duration=60
                        )
                        logger.info(f"[Trace] [execute_league_match] Thread created successfully with ID {thread.id}. Posting intro rules...")
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
                        
                        logger.info(f"[Trace] [execute_league_match] Saving thread ID {thread.id} to guild_config...")
                        await db.table("guild_config").update({"league_updates_thread_id": thread.id}).eq("guild_id", guild_id).execute()
                        logger.info(f"[Trace] [execute_league_match] Thread ID {thread.id} successfully confirmed in DB.")
                    except Exception as e:
                        logger.exception("Failed to create League Journal thread.")
                        await interaction.followup.send(embed=error_embed(f"Failed to create League Journal thread: {e}"), ephemeral=True)
                        return
                else:
                    logger.info(f"[Trace] [execute_league_match] Reusing existing thread {thread.id}.")

            logger.info(f"[Trace] [execute_league_match] Released lock for guild {guild_id}.")

            # Instantiate LeagueMatchHandler
            handler = LeagueMatchHandler(thread, fixture_id=fixture["id"], season_id=fixture["season_id"])
            
            await interaction.followup.send(embed=success_embed(f"⚔️ **Match has kicked off!** Follow commentary in {thread.mention}."), ephemeral=True)

            await run_league_match_simulation(
                bot=self.bot,
                db=db,
                guild=interaction.guild,
                fixture=f,
                active_player_id=user_id,
                handler=handler
            )
            
            # Check matchday advancement
            from apps.discord_bot.cogs.league_cog import update_current_matchday
            await update_current_matchday(db, f["season_id"])
        except Exception as e:
            logger.exception("Failed to execute league match.")
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed(f"An error occurred: {str(e)}"), ephemeral=True)
        finally:
            if lock_acquired:
                await db.table("match_locks").delete().eq("discord_id", user_id).execute()

    async def start_friendly_match(
        self,
        interaction: discord.Interaction,
        challenger: discord.Member | discord.User,
        opponent: discord.Member,
        invitation_msg: discord.Message
    ) -> None:
        db = await get_client()
        
        locks_res = await db.table("match_locks").select("discord_id").in_("discord_id", [challenger.id, opponent.id]).execute()
        if locks_res.data:
            await invitation_msg.channel.send(
                embed=error_embed("One or both managers are already in another match."),
            )
            return

        # 1. Spawning Thread
        thread = None
        try:
            c_res = await db.table("players").select("*").eq("discord_id", challenger.id).maybe_single().execute()
            o_res = await db.table("players").select("*").eq("discord_id", opponent.id).maybe_single().execute()
            
            c_player = c_res.data
            o_player = o_res.data
            
            thread_name = f"🤝 {c_player['club_name']} vs {o_player['club_name']} – Friendly"
            thread = await invitation_msg.create_thread(
                name=thread_name,
                auto_archive_duration=60
            )
        except Exception as e:
            logger.exception("Failed to spawn friendly match thread.")
            await invitation_msg.channel.send(embed=error_embed(f"Failed to create match thread: {str(e)}"))
            return

        # 2. Acquire Concurrency Locks
        try:
            await db.table("match_locks").upsert([
                {"discord_id": challenger.id, "lock_type": "friendly"},
                {"discord_id": opponent.id, "lock_type": "friendly"}
            ]).execute()
        except Exception as e:
            logger.exception("Failed to acquire match locks.")
            await thread.send(embed=error_embed(f"Failed to acquire match locks: {str(e)}"))
            return

        try:
            async def get_squad_cards(discord_id: int):
                assignments_res = await db.table("squad_assignments").select("position_slot, player_cards(*)").eq("discord_id", discord_id).execute()
                assignments = assignments_res.data or []
                active_cards = [a["player_cards"] for a in assignments if a.get("player_cards")]
                
                match_cards = []
                for c in active_cards:
                    ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", c["id"]).execute()
                    playstyles = [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []
                    match_cards.append(
                        MatchPlayerCard(
                            name=c["name"], position=c["position"], overall=c["overall"],
                            pac=c.get("pac", 50), sho=c.get("sho", 50), pas=c.get("pas", 50),
                            dri=c.get("dri", 50), def_stat=c.get("def", 50), phy=c.get("phy", 50),
                            morale=c.get("morale", 80), playstyles=playstyles
                        )
                    )
                return match_cards
            
            c_cards = await get_squad_cards(challenger.id)
            o_cards = await get_squad_cards(opponent.id)
            
            if len(c_cards) != 11 or len(o_cards) != 11:
                error_msg = ""
                if len(c_cards) != 11:
                    error_msg += f"❌ Challenger **{c_player['manager_name']}** has {len(c_cards)}/11 players assigned.\n"
                if len(o_cards) != 11:
                    error_msg += f"❌ Opponent **{o_player['manager_name']}** has {len(o_cards)}/11 players assigned.\n"
                await thread.send(embed=error_embed(f"Friendly match cancelled:\n{error_msg}Managers must have exactly 11 active squad players to start."))
                return

            c_rating = sum(p.overall for p in c_cards) / 11
            o_rating = sum(p.overall for p in o_cards) / 11

            # 3. Initialize Engine
            state = MatchState(home_rating=c_rating, away_rating=o_rating)
            commentary_engine = CommentaryEngine()

            init_embed = discord.Embed(
                title=f"🏟️ Live Friendly Match: {c_player['club_name']} vs {o_player['club_name']}",
                color=0x00FF87
            )
            init_embed.add_field(name="Scoreboard", value=f"🏟️ **{c_player['club_name']}** `0 - 0` **{o_player['club_name']}**", inline=False)
            init_embed.add_field(name="📈 Momentum", value=get_momentum_bar(0), inline=False)
            init_embed.add_field(name="Live Commentary", value="🟢 **0'** - The referee blows the whistle and we are underway!", inline=False)
            
            ticker_msg = await thread.send(embed=init_embed)

            # Ticker Streaming Loop
            ticker_history: list[str] = []
            key_events_list: list[dict] = []
            
            async for ev in stream_match(state, c_cards, o_cards, c_player["club_name"], o_player["club_name"]):
                variables = {
                    "actor": ev["actor"],
                    "team": ev["team"]
                }
                comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
                text = comm["text"]
                urgency = comm["urgency"]

                emoji_map = {
                    "KICKOFF": "🟢",
                    "HALF_TIME": "⏸️",
                    "GOAL": "⚽",
                    "SAVE": "🧤",
                    "MISS": "❌",
                    "CHANCE": "🎯",
                    "FOUL": "🟨",
                    "FULL_TIME": "🏁"
                }
                emo = emoji_map.get(ev["type"], "⏱️")

                ticker_history.append(f"{emo} **{ev['minute']}'** - {text}")
                recent_ticker = ticker_history[-5:]

                embed = discord.Embed(
                    title=f"🏟️ Live Friendly Match: {c_player['club_name']} vs {o_player['club_name']}",
                    color=0x00FF87
                )
                embed.add_field(name="Scoreboard", value=f"🏟️ **{c_player['club_name']}** `{ev['score_update']}` **{o_player['club_name']}**", inline=False)
                embed.add_field(name="📈 Momentum", value=get_momentum_bar(state.momentum), inline=False)
                embed.add_field(name="Live Commentary", value="\n".join(recent_ticker), inline=False)

                await ticker_msg.edit(embed=embed)

                if ev["type"] in ["KICKOFF", "HALF_TIME", "GOAL", "SAVE", "MISS", "CHANCE", "FOUL", "FULL_TIME"]:
                    event_entry = {
                        "minute": ev["minute"],
                        "type": ev["type"],
                        "actor": ev["actor"],
                        "team": ev["team"],
                        "text": text
                    }
                    if "assister" in ev:
                        event_entry["assister"] = ev["assister"]
                    key_events_list.append(event_entry)

                if ev["type"] in ["FULL_TIME", "HALF_TIME"]:
                    sleep_time = 2.0
                elif urgency == "cliffhanger":
                    sleep_time = 3.5
                elif urgency == "build_up":
                    sleep_time = 2.5
                else:
                    sleep_time = 1.5

                await asyncio.sleep(sleep_time)

            # Generate Match Statistics
            box_score = {
                "possession_home": random.randint(45, 55),
                "possession_away": random.randint(45, 55),
                "shots_home": max(state.home_score + 1, random.randint(5, 12)),
                "shots_away": max(state.away_score + 1, random.randint(5, 12)),
                "motm": random.choice(c_cards + o_cards).name
            }

            press_embed = discord.Embed(
                title="🎙️ Friendly Post-Match Press Conference",
                description="Reporters gather as the managers discuss the friendly game statistics.",
                color=0xFFCC00
            )
            result_emoji = "🤝 DRAW" if state.home_score == state.away_score else ("🎉 HOME WIN" if state.home_score > state.away_score else "🎉 AWAY WIN")
            press_embed.add_field(
                name="🥅 Final Result",
                value=f"### {result_emoji}\n**{c_player['club_name']}** `{state.home_score} - {state.away_score}` **{o_player['club_name']}**",
                inline=False
            )
            press_embed.add_field(
                name="📊 Match Statistics",
                value=(
                    f"**Possession**: {box_score['possession_home']}% - {box_score['possession_away']}%\n"
                    f"**Shots**: {box_score['shots_home']} - {box_score['shots_away']}\n"
                    f"**Man of the Match**: ⭐ **{box_score['motm']}**"
                ),
                inline=True
            )
            press_embed.set_footer(text="🤝 Match concluded. Friendly match logs are completely isolated.")
            
            await thread.send(content=f"🏁 Match finished! {challenger.mention} {opponent.mention}", embed=press_embed)

            # Write friendly match log
            await db.table("friendly_match_logs").insert({
                "home_discord_id": challenger.id,
                "away_discord_id": opponent.id,
                "home_score": state.home_score,
                "away_score": state.away_score,
                "box_score": box_score,
                "key_events": key_events_list
            }).execute()

            # Edit thread name
            try:
                await thread.edit(name=f"🤝 {c_player['club_name']} {state.home_score}-{state.away_score} {o_player['club_name']} – Friendly")
            except Exception as e:
                logger.warning(f"Failed to rename friendly thread: {e}")

            # Schedule Thread Archival and Lock after 120 seconds
            async def archive_friendly_thread(t: discord.Thread, delay: float) -> None:
                await asyncio.sleep(delay)
                try:
                    await t.edit(locked=True, archived=True)
                except discord.NotFound:
                    pass
                except Exception as err:
                    logger.warning(f"Failed to lock and archive friendly thread {t.id}: {err}")

            asyncio.create_task(archive_friendly_thread(thread, 120.0))

        except Exception as e:
            logger.exception("Error during friendly match execution.")
            await thread.send(embed=error_embed(f"An error occurred during friendly match execution: {str(e)}"))
        finally:
            # Release Locks
            await db.table("match_locks").delete().in_("discord_id", [challenger.id, opponent.id]).execute()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))

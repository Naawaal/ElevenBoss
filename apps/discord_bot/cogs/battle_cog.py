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
    collect_match_events,
    MatchResult,
    format_zone_breakdown,
)
from apps.discord_bot.core.match_cards import card_from_db_row, fetch_playstyles
from apps.discord_bot.core.economy_rpc import sync_action_energy, match_energy_cost, economy_v2_enabled
from apps.discord_bot.core.league_rewards import apply_league_human_rewards
from apps.discord_bot.core.match_rewards import apply_bot_match_rewards
from apps.discord_bot.core.competitive_display import format_bot_rewards_block, format_season_reward_line
from leagues import division_rank_points, global_lp_delta, clamp_global_lp
from apps.discord_bot.core.thread_permissions import (
    MATCH_THREAD_ARCHIVE_DELAY_SEC,
    archive_thread_after_delay,
)
from apps.discord_bot.core.league_journal import (
    get_or_create_league_journal,
    post_journal_result_line,
    post_matchday_result_line,
    post_journal_standings,
    persist_journal_standings_message_id,
    resolve_season_threads,
)
from apps.discord_bot.core.pitch_generator import generate_squad_pitch
from leagues import format_standings_table, tie_breaker_footer
from apps.discord_bot.core.match_runs import (
    abandon_run,
    build_league_snapshot,
    complete_run,
    create_ephemeral_run,
    create_league_run,
    generate_sim_seed,
    get_active_fixture_run,
    mark_completing,
    squads_from_snapshot,
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


def _match_stats_from_state(state: MatchState) -> tuple[int, int, int, int]:
    """Possession and shots derived from NSS live counters."""
    ls = state.live_stats
    return (
        ls.possession_home_pct(),
        ls.possession_away_pct(),
        ls.home_shots,
        ls.away_shots,
    )


MATCH_ENGINE_FOOTER = (
    "Zone OVR (GK/DEF/MID/ATT) drives phase rolls. Training stats shape OVR; "
    "morale and PlayStyles apply at kickoff."
)

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
        self.state.pending_home_momentum = 5.0
        await interaction.response.send_message("📣 **Touchline**: Tactical focus shifted to **Attack**!", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⚖️ Balanced", custom_id="battle_touchline_balanced")
    async def balanced_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 1.0
        self.state.pending_home_momentum = 0.0
        await interaction.response.send_message("📣 **Touchline**: Tactics set to **Balanced** shape.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🛡️ Defend", custom_id="battle_touchline_defend")
    async def defend_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.home_tactics_modifier = 0.7
        self.state.pending_home_momentum = -5.0
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
        zone_home = kwargs.get("zone_home")
        zone_away = kwargs.get("zone_away")
        if zone_home and zone_away:
            press_embed.add_field(
                name="📐 Zone Strengths",
                value=f"{zone_home}\n{zone_away}",
                inline=False,
            )
        
        lp_change = kwargs.get("lp_change")
        global_divisions = kwargs.get("global_divisions") or []
        weekly_total = kwargs.get("weekly_total", 0)
        new_lp = kwargs.get("total_lp", 0)

        if lp_change is not None and global_divisions:
            rewards_value = format_bot_rewards_block(
                coins=active_earned,
                div_pts_earned=active_pts,
                weekly_total=weekly_total,
                lp_delta=lp_change,
                new_lp=new_lp,
                divisions=global_divisions,
            )
        else:
            rewards_value = f"🪙 **+{active_earned} coins**"
            if active_pts > 0:
                rewards_value += f"\n📊 **+{active_pts} Division Rank**"

        press_embed.add_field(
            name="🎁 Rewards",
            value=rewards_value,
            inline=True
        )
        press_embed.set_footer(
            text=f"✅ Rewards saved. Check `/leaderboard` for rankings. {MATCH_ENGINE_FOOTER}"
        )
        await target.send(embed=press_embed)

        if self.thread and self.thread.guild:
            try:
                await self.thread.edit(name=f"🏆 {home_name} {result.goals_for}-{result.goals_against} {away_name}")
            except Exception as e:
                logger.warning(f"Failed to rename thread: {e}")

            asyncio.create_task(
                archive_thread_after_delay(
                    self.thread,
                    self.thread.guild,
                    delay=MATCH_THREAD_ARCHIVE_DELAY_SEC,
                )
            )

class LeagueReactionView(discord.ui.View):
    """Post-match social buttons (US-26)."""
    def __init__(self, opponent_id: int | None) -> None:
        super().__init__(timeout=300)
        self.opponent_id = opponent_id

    @discord.ui.button(label="🤝 GG", style=discord.ButtonStyle.success, custom_id="league_gg")
    async def gg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🤝 Good game!", ephemeral=True)

    @discord.ui.button(label="👉 Poke Opponent", style=discord.ButtonStyle.secondary, custom_id="league_poke")
    async def poke_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.opponent_id:
            await interaction.response.send_message(
                f"<@{self.opponent_id}> — **{interaction.user.display_name}** pokes you after the match! 👉",
                ephemeral=False,
            )
        else:
            await interaction.response.send_message("No opponent to poke.", ephemeral=True)


class LeagueMatchHandler(IMatchOutputHandler):
    def __init__(
        self,
        commentary_thread: discord.Thread,
        fixture_id: str | None = None,
        season_id: str | None = None,
        *,
        journal_thread: discord.Thread | None = None,
        journal_standings_msg_id: int | None = None,
    ) -> None:
        self.commentary_thread = commentary_thread
        self.output_thread = commentary_thread
        self.journal_thread = journal_thread
        self.fixture_id = fixture_id
        self.season_id = season_id
        self.journal_standings_msg_id = journal_standings_msg_id
        self.ticker_msg = None
        self.live_table_msg_id: int | None = journal_standings_msg_id

    async def post_prematch_lineups(
        self,
        home_name: str,
        away_name: str,
        home_cards: list[dict],
        away_cards: list[dict],
        formation: str = "4-4-2",
    ) -> None:
        """Post pitch images for both XIs before kickoff."""
        try:
            home_pitch = await generate_squad_pitch(formation, home_cards[:11])
            await self.commentary_thread.send(content=f"📋 **{home_name}** — Starting XI", file=home_pitch)
            if away_cards:
                away_pitch = await generate_squad_pitch(formation, away_cards[:11])
                await self.commentary_thread.send(content=f"📋 **{away_name}** — Starting XI", file=away_pitch)
        except Exception:
            logger.debug("Prematch pitch render skipped", exc_info=True)

    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None) -> discord.abc.Messageable:
        return self.commentary_thread

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
        zone_home = kwargs.get("zone_home")
        zone_away = kwargs.get("zone_away")
        if zone_home and zone_away:
            press_embed.add_field(
                name="📐 Zone Strengths",
                value=f"{zone_home}\n{zone_away}",
                inline=False,
            )

        rewards_text = ""
        db = await get_client()
        home_res = await db.table("players").select("is_ai").eq("discord_id", home_team_id).maybe_single().execute()
        home_p = home_res.data if home_res else None
        away_res = await db.table("players").select("is_ai").eq("discord_id", away_team_id).maybe_single().execute()
        away_p = away_res.data if away_res else None

        kw_home_coins = kwargs.get("home_coins")
        kw_away_coins = kwargs.get("away_coins")
        kw_home_pts = kwargs.get("home_pts")
        kw_away_pts = kwargs.get("away_pts")
        if kw_home_coins is not None and kw_home_pts is not None:
            rewards_text += format_season_reward_line(home_name, kw_home_coins, kw_home_pts, prefix="🏡 ") + "\n"
            if kwargs.get("home_milestone"):
                rewards_text += f"⭐ **{home_name}** Matchday Milestone: +{kwargs['home_milestone']} coins!\n"
        if kw_away_coins is not None and kw_away_pts is not None:
            rewards_text += format_season_reward_line(away_name, kw_away_coins, kw_away_pts, prefix="✈️ ") + "\n"
            if kwargs.get("away_milestone"):
                rewards_text += f"⭐ **{away_name}** Matchday Milestone: +{kwargs['away_milestone']} coins!\n"

        if rewards_text:
            press_embed.add_field(name="🎁 Match Rewards", value=rewards_text.strip(), inline=True)

        press_embed.set_footer(
            text=f"✅ Season Pts updated. `/leaderboard` → Season tab. {MATCH_ENGINE_FOOTER}"
        )

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

        opponent_id = away_team_id if user_id == home_team_id else home_team_id
        reaction_view = LeagueReactionView(opponent_id if opponent_id else None)

        await self.commentary_thread.send(
            content=congrat_ping if congrat_ping else None,
            embed=press_embed,
            view=reaction_view,
        )

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
                        card_goals = sum(
                            1 for ev in result.key_events
                            if ev.get("type") == "GOAL" and ev.get("team") == home_name
                            and ev.get("actor") and ev.get("actor") != "Unknown"
                        )
                        new_goals = old["goals"] + card_goals
                        home_assists = sum(
                            1 for ev in result.key_events
                            if ev.get("type") == "GOAL" and ev.get("team") == home_name and ev.get("assister")
                        )
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
                        card_goals = sum(
                            1 for ev in result.key_events
                            if ev.get("type") == "GOAL" and ev.get("team") == away_name
                            and ev.get("actor") and ev.get("actor") != "Unknown"
                        )
                        new_goals = old["goals"] + card_goals
                        away_assists = sum(
                            1 for ev in result.key_events
                            if ev.get("type") == "GOAL" and ev.get("team") == away_name and ev.get("assister")
                        )
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
                        await db.table("player_season_stats").upsert(stats_to_upsert).execute()
                        logger.info(f"[finalize_match] Upserted player_season_stats for season {self.season_id}")
            except Exception as se:
                logger.error(f"Failed to update player season stats: {se}", exc_info=True)

async def run_league_match_simulation(
    bot: commands.Bot,
    db,
    guild: discord.Guild,
    fixture: dict,
    active_player_id: int | None,
    handler: IMatchOutputHandler,
    *,
    sim_seed: int | None = None,
    run_id: str | None = None,
    recovery: bool = False,
    silent: bool = False,
) -> None:
    home_p = fixture["home"]
    away_p = fixture["away"]
    fixture_id = fixture["id"]

    if fixture.get("is_played") and not recovery:
        logger.info("Fixture %s already played; skipping simulation.", fixture_id)
        return

    home_squad: list[MatchPlayerCard] = []
    home_rating = 60.0
    home_cards: list[dict] = []
    away_squad: list[MatchPlayerCard] = []
    away_rating = 60.0
    away_cards: list[dict] = []

    if recovery and run_id:
        run_res = await db.table("match_runs").select("squad_snapshot").eq("id", run_id).maybe_single().execute()
        snapshot = (run_res.data or {}).get("squad_snapshot") or {}
        home_squad, away_squad = squads_from_snapshot(snapshot)
        home_rating = float(snapshot.get("home_rating", 60.0))
        away_rating = float(snapshot.get("away_rating", 60.0))
        home_name = snapshot.get("home_name", home_p["club_name"])
        away_name = snapshot.get("away_name", away_p["club_name"])
        home_cards = [{"id": cid} for cid in snapshot.get("home_card_ids", [])]
        away_cards = [{"id": cid} for cid in snapshot.get("away_card_ids", [])]
    else:
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
                playstyles = await fetch_playstyles(db, c["id"])
                home_squad.append(card_from_db_row(c, playstyles))
            if home_squad:
                home_rating = sum(p.overall for p in home_squad) / len(home_squad)

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
                playstyles = await fetch_playstyles(db, c["id"])
                away_squad.append(card_from_db_row(c, playstyles))
            if away_squad:
                away_rating = sum(p.overall for p in away_squad) / len(away_squad)

        home_name = home_p["club_name"] + (" (AI)" if home_p["is_ai"] else "")
        away_name = away_p["club_name"] + (" (AI)" if away_p["is_ai"] else "")

        # Lineup familiarity bonus (US-26)
        if not recovery:
            from apps.discord_bot.core.league_rewards import league_familiarity_multiplier
            season_id = fixture.get("season_id")
            if season_id and not home_p["is_ai"] and len(home_cards) == 11:
                home_rating *= await league_familiarity_multiplier(
                    db, season_id=season_id, discord_id=int(fixture["home_team_id"]),
                    current_card_ids=[c["id"] for c in home_cards],
                )
            if season_id and not away_p["is_ai"] and len(away_cards) == 11:
                away_rating *= await league_familiarity_multiplier(
                    db, season_id=season_id, discord_id=int(fixture["away_team_id"]),
                    current_card_ids=[c["id"] for c in away_cards],
                )

    sim_seed = sim_seed if sim_seed is not None else generate_sim_seed()
    match_rng = random.Random(sim_seed)

    if not recovery and not run_id:
        existing = await get_active_fixture_run(db, fixture_id)
        if existing:
            raise RuntimeError("This fixture is already being played.")

        thread_id = getattr(getattr(handler, "output_thread", None), "id", None)
        run_row = await create_league_run(
            db,
            fixture_id=fixture_id,
            active_discord_id=active_player_id,
            sim_seed=sim_seed,
            squad_snapshot=build_league_snapshot(
                fixture=fixture,
                home_name=home_name,
                away_name=away_name,
                home_rating=home_rating,
                away_rating=away_rating,
                home_squad=home_squad,
                away_squad=away_squad,
                home_cards=home_cards,
                away_cards=away_cards,
            ),
            guild_id=guild.id if guild else None,
            thread_id=thread_id,
            home_discord_id=int(fixture["home_team_id"]),
            away_discord_id=int(fixture["away_team_id"]),
        )
        run_id = run_row.get("id", run_id)

    state = MatchState(home_rating=home_rating, away_rating=away_rating)
    commentary_engine = CommentaryEngine()
    target = await handler.initialize(None, home_name, away_name, fixture["matchday"])

    touchline_user_id = active_player_id if active_player_id else 0
    touchline_view = TouchlineView(state, touchline_user_id) if touchline_user_id and not silent else None

    if not silent:
        # Pre-match lineup pitches (human squads only)
        home_pitch_cards = [
            {"name": c.get("name", "Player"), "overall": c.get("overall", 50), "position": c.get("position", "MID")}
            for c in home_cards
        ] if home_cards and not home_p["is_ai"] else []
        away_pitch_cards = [
            {"name": c.get("name", "Player"), "overall": c.get("overall", 50), "position": c.get("position", "MID")}
            for c in away_cards
        ] if away_cards and not away_p["is_ai"] else []
        if hasattr(handler, "post_prematch_lineups") and (home_pitch_cards or away_pitch_cards):
            await handler.post_prematch_lineups(home_name, away_name, home_pitch_cards, away_pitch_cards)
        await handler.start_match(target, home_name, away_name, touchline_view)

    ticker_history: list[str] = []
    key_events_list: list[dict] = []

    async def _consume_event(ev: dict) -> None:
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
        if ev["type"] in ["KICKOFF", "HALF_TIME", "GOAL", "YELLOW_CARD", "INJURY", "FULL_TIME"]:
            event_entry = {
                "minute": ev["minute"],
                "type": ev["type"],
                "actor": ev["actor"],
                "team": ev["team"],
                "text": text,
            }
            if "assister" in ev:
                event_entry["assister"] = ev["assister"]
            key_events_list.append(event_entry)
        if not silent:
            await handler.update_ticker(ev, state, ticker_history[-5:], touchline_view)
            if ev["type"] in ["FULL_TIME", "HALF_TIME"]:
                sleep_time = 2.0
            elif urgency == "cliffhanger":
                sleep_time = 2.0
            elif urgency == "build_up":
                sleep_time = 1.5
            else:
                sleep_time = 1.0
            await asyncio.sleep(sleep_time)

    if silent:
        state, events = await collect_match_events(
            state, home_squad, away_squad, home_name, away_name, sim_seed
        )
        for ev in events:
            variables = {"actor": ev["actor"], "team": ev["team"]}
            comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
            if ev["type"] in ["KICKOFF", "HALF_TIME", "GOAL", "YELLOW_CARD", "INJURY", "FULL_TIME"]:
                entry = {
                    "minute": ev["minute"],
                    "type": ev["type"],
                    "actor": ev["actor"],
                    "team": ev["team"],
                    "text": comm["text"],
                }
                if "assister" in ev:
                    entry["assister"] = ev["assister"]
                key_events_list.append(entry)
    else:
        async for ev in stream_match(
            state, home_squad, away_squad, home_name, away_name, rng=match_rng
        ):
            await _consume_event(ev)

    if touchline_view:
        for child in touchline_view.children:
            child.disabled = True

    if run_id:
        await mark_completing(db, run_id)

    home_result_str = "win" if state.home_score > state.away_score else ("draw" if state.home_score == state.away_score else "loss")
    away_result_str = "win" if state.away_score > state.home_score else ("draw" if state.home_score == state.away_score else "loss")

    stats_rng = random.Random(sim_seed ^ 0xABCDEF)
    all_human_cards = home_squad if not home_p["is_ai"] else (away_squad if not away_p["is_ai"] else [])
    poss_h, poss_a, shots_h, shots_a = _match_stats_from_state(state)
    motm = state.live_stats.pick_motm(
        stats_rng.choice(all_human_cards).name if all_human_cards else "AI Match MVP"
    )

    h_coins = a_coins = 0
    h_pts = a_pts = 0
    h_milestone = a_milestone = None

    if not home_p["is_ai"]:
        h_coins, h_pts = await apply_league_human_rewards(
            db,
            player_id=int(fixture["home_team_id"]),
            player_row=home_p,
            result_str=home_result_str,
            fixture_id=fixture_id,
            run_id=run_id,
            cards=home_cards,
            club_name=home_p["club_name"],
            team_rating=home_rating,
            motm_name=motm,
            key_events=key_events_list,
            goals_for=state.home_score,
            goals_against=state.away_score,
            deduct_energy=(active_player_id == fixture["home_team_id"]),
        )
        from apps.discord_bot.core.league_rewards import check_matchday_milestone
        h_milestone = await check_matchday_milestone(
            db, player_id=int(fixture["home_team_id"]), season_id=fixture["season_id"],
            matchday=fixture["matchday"], points_earned=h_pts,
        )

    if not away_p["is_ai"]:
        a_coins, a_pts = await apply_league_human_rewards(
            db,
            player_id=int(fixture["away_team_id"]),
            player_row=away_p,
            result_str=away_result_str,
            fixture_id=fixture_id,
            run_id=run_id,
            cards=away_cards,
            club_name=away_p["club_name"],
            team_rating=away_rating,
            motm_name=motm,
            key_events=key_events_list,
            goals_for=state.away_score,
            goals_against=state.home_score,
            deduct_energy=(active_player_id == fixture["away_team_id"]),
        )
        from apps.discord_bot.core.league_rewards import check_matchday_milestone
        a_milestone = await check_matchday_milestone(
            db, player_id=int(fixture["away_team_id"]), season_id=fixture["season_id"],
            matchday=fixture["matchday"], points_earned=a_pts,
        )

    await db.table("league_fixtures").update({
        "home_score": state.home_score,
        "away_score": state.away_score,
        "is_played": True,
        "played_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", fixture_id).execute()

    # Live standings + result line in journal (dual_v2) or commentary thread (legacy)
    if not silent and handler.season_id:
        standings_target = getattr(handler, "journal_thread", None) or handler.commentary_thread
        try:
            from apps.discord_bot.cogs.league_cog import fetch_standings
            fixtures_res = await db.table("league_fixtures").select("*").eq("season_id", handler.season_id).execute()
            all_fixtures = fixtures_res.data or []
            standings = await fetch_standings(db, handler.season_id)
            table_text = format_standings_table(standings, all_fixtures, limit=10)
            existing_id = getattr(handler, "journal_standings_msg_id", None) or getattr(handler, "live_table_msg_id", None)
            msg = await post_journal_standings(
                standings_target,
                table_text,
                fixture["matchday"],
                existing_message_id=existing_id,
            )
            if msg:
                if not getattr(handler, "journal_standings_msg_id", None):
                    handler.journal_standings_msg_id = msg.id
                    handler.live_table_msg_id = msg.id
                    if handler.journal_thread:
                        await persist_journal_standings_message_id(db, handler.season_id, msg.id)
            if handler.journal_thread:
                await post_journal_result_line(
                    handler.journal_thread,
                    fixture["matchday"],
                    home_name,
                    away_name,
                    state.home_score,
                    state.away_score,
                )
            if handler.commentary_thread and guild:
                await post_matchday_result_line(
                    handler.commentary_thread,
                    guild,
                    db,
                    fixture["matchday"],
                    home_name,
                    away_name,
                    state.home_score,
                    state.away_score,
                )
        except Exception:
            logger.debug("Journal standings update skipped", exc_info=True)
    all_human_cards = home_squad if not home_p["is_ai"] else (away_squad if not away_p["is_ai"] else [])
    poss_h, poss_a, shots_h, shots_a = _match_stats_from_state(state)
    motm = state.live_stats.pick_motm(
        stats_rng.choice(all_human_cards).name if all_human_cards else "AI Match MVP"
    )

    match_res = MatchResult(
        result="win" if state.home_score != state.away_score else "draw",
        goals_for=state.home_score,
        goals_against=state.away_score,
        my_rating=home_rating,
        opponent_rating=away_rating,
        possession_home=poss_h,
        possession_away=poss_a,
        shots_home=shots_h,
        shots_away=shots_a,
        motm=motm,
        coins_earned=h_coins if active_player_id == fixture["home_team_id"] else a_coins,
        points_earned=h_pts if active_player_id == fixture["home_team_id"] else a_pts,
        key_events=key_events_list
    )

    active_earned = h_coins if active_player_id == fixture["home_team_id"] else a_coins
    active_pts = h_pts if active_player_id == fixture["home_team_id"] else a_pts

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
        away_team_id=fixture["away_team_id"],
        zone_home=format_zone_breakdown(home_squad, home_name),
        zone_away=format_zone_breakdown(away_squad, away_name),
        home_coins=h_coins if not home_p["is_ai"] else None,
        away_coins=a_coins if not away_p["is_ai"] else None,
        home_pts=h_pts if not home_p["is_ai"] else None,
        away_pts=a_pts if not away_p["is_ai"] else None,
        home_milestone=h_milestone,
        away_milestone=a_milestone,
    )

    if run_id:
        await complete_run(db, run_id, home_score=state.home_score, away_score=state.away_score)

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
                f"Choose your competitive match pathway below. Bot battles consume **20** ⚡ action energy.\n"
                f"Friendly matches are **free** — no energy, no coins, no XP."
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

    @battle_group.command(name="how-it-works", description="How the NSS match engine uses your squad.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def how_it_works(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="⚙️ How Matches Work (NSS Engine)",
            description=(
                "ElevenBoss simulates matches as a **phase-by-phase** highlight reel — not minute-by-minute physics.\n\n"
                "**What matters in each phase:**\n"
                "• **Midfield** — MID zone strength (+ home edge)\n"
                "• **Build-up** — PAS vs DEF\n"
                "• **Attack** — DRI/ATT vs DEF\n"
                "• **Counter** — PAC vs DEF\n"
                "• **Shot** — SHO vs GK\n\n"
                "**Your squad rating** is the average of **zone OVR** (GK / DEF / MID / ATT) from your starting XI.\n"
                "Training stats feed into OVR; **morale** and **PlayStyles** adjust kickoff strength.\n\n"
                "**Variance is real:** a +10 OVR squad still loses ~10% of matches. Upsets happen — "
                "they are not bugs.\n\n"
                "**Post-match stats** (possession, shots) are counted from the live simulation, "
                "not random numbers."
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=MATCH_ENGINE_FOOTER)
        await interaction.followup.send(embed=embed, ephemeral=True)

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
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        lock_acquired = False
        bot_run_id: str | None = None
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

            # 2. Check action energy (economy v2)
            v2 = await economy_v2_enabled(db)
            energy_row = await sync_action_energy(db, interaction.user.id)
            curr_energy = energy_row.get("action_energy", player.get("action_energy", 0))
            needed = match_energy_cost("bot", v2=v2)
            if curr_energy < needed:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Insufficient energy. Bot matches require **{needed}** ⚡ (you have **{curr_energy}**)."
                    ),
                    ephemeral=True,
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
 
            # 4. Construct MatchPlayerCard models including morale-adjusted OVR
            match_cards = []
            for c in active_cards:
                playstyles = await fetch_playstyles(db, c["id"])
                match_cards.append(card_from_db_row(c, playstyles))
 
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

            sim_seed = generate_sim_seed()
            run_row = await create_ephemeral_run(
                db,
                run_type="bot",
                active_discord_id=interaction.user.id,
                home_discord_id=interaction.user.id,
                away_discord_id=None,
                sim_seed=sim_seed,
                guild_id=interaction.guild_id,
                thread_id=getattr(handler.thread, "id", None),
            )
            bot_run_id = run_row.get("id")

            touchline_view = TouchlineView(state, interaction.user.id)
            await handler.start_match(target, player["club_name"], opp_name, touchline_view)

            opp_squad = [
                MatchPlayerCard(name="Opponent Striker", position="FWD", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Midfielder", position="MID", overall=int(opp_rating)),
                MatchPlayerCard(name="Opponent Defender", position="DEF", overall=int(opp_rating)),
            ]

            match_rng = random.Random(sim_seed)
            # Commentary Streaming Loop
            ticker_history: list[str] = []
            key_events_list: list[dict] = []

            async for ev in stream_match(
                state, match_cards, opp_squad, player["club_name"], opp_name, rng=match_rng
            ):
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

                if ev["type"] in ["KICKOFF", "HALF_TIME", "GOAL", "MISS", "CHANCE", "FOUL", "FULL_TIME"]:
                    event_entry = {
                        "minute": ev["minute"],
                        "type": ev["type"],
                        "actor": ev["actor"],
                        "team": ev["team"],
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

            for child in touchline_view.children:
                child.disabled = True
            
            # Generate MatchResult and rewards
            win_coins = current_div["win_coins"]
            res_str = "win" if state.home_score > state.away_score else (
                "draw" if state.home_score == state.away_score else "loss"
            )
            points_earned = division_rank_points(res_str)
            lp_delta = global_lp_delta(res_str)
            new_lp, actual_lp_change = clamp_global_lp(user_lp, lp_delta)

            poss_h, poss_a, shots_h, shots_a = _match_stats_from_state(state)
            motm = state.live_stats.pick_motm(random.choice(match_cards).name)

            coins_earned = await apply_bot_match_rewards(
                db,
                player_id=interaction.user.id,
                player_row=player,
                result_str=res_str,
                cards=active_cards,
                club_name=player["club_name"],
                team_rating=my_rating,
                opponent_rating=opp_rating,
                goals_for=state.home_score,
                goals_against=state.away_score,
                points_earned=points_earned,
                lp_change=lp_delta,
                division_win_coins=win_coins,
                run_id=bot_run_id,
                motm_name=motm,
                key_events=key_events_list,
            )

            result = MatchResult(
                result=res_str,
                goals_for=state.home_score,
                goals_against=state.away_score,
                my_rating=my_rating,
                opponent_rating=opp_rating,
                coins_earned=coins_earned,
                points_earned=points_earned,
                possession_home=poss_h,
                possession_away=poss_a,
                shots_home=shots_h,
                shots_away=shots_a,
                motm=motm
            )

            weekly_total = int(player.get("league_points", 0)) + points_earned

            await handler.finalize_match(
                result=result,
                state=state,
                home_name=player["club_name"],
                away_name=opp_name,
                motm=motm,
                active_earned=result.coins_earned,
                active_pts=result.points_earned,
                user_id=interaction.user.id,
                home_team_id=interaction.user.id,
                away_team_id=0,
                zone_home=format_zone_breakdown(match_cards, player["club_name"]),
                zone_away=format_zone_breakdown(opp_squad, opp_name),
                lp_change=actual_lp_change,
                total_lp=new_lp,
                weekly_total=weekly_total,
                global_divisions=divisions,
            )
            if bot_run_id:
                await complete_run(db, bot_run_id, home_score=state.home_score, away_score=state.away_score)
        except Exception as e:
            logger.exception("Failed to simulate match.")
            if bot_run_id:
                await abandon_run(db, bot_run_id)
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

            active_run = await get_active_fixture_run(db, fixture_id)
            if active_run:
                await interaction.followup.send(
                    embed=error_embed("This fixture is already being played. Try again shortly."),
                    ephemeral=True,
                )
                return

            season_res = await db.table("league_seasons").select("status").eq("id", f["season_id"]).maybe_single().execute()
            if season_res.data and season_res.data.get("status") == "paused":
                await interaction.followup.send(embed=error_embed("Season is paused. Wait for admin to resume."), ephemeral=True)
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

            # 11-player XI guard
            assignments_res = await db.table("squad_assignments").select("player_card_id").eq("discord_id", user_id).execute()
            xi_count = len(assignments_res.data or [])
            if xi_count != 11:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Your starting squad must have exactly **11 players** assigned (current: **{xi_count}/11**).\n"
                        "Configure your starting 11 using `/squad` first."
                    ),
                    ephemeral=True,
                )
                return

            v2 = await economy_v2_enabled(db)
            if v2:
                energy_row = await sync_action_energy(db, user_id)
                curr_energy = energy_row.get("action_energy", active_p.get("action_energy", 0))
                needed = match_energy_cost("league", v2=True)
                if curr_energy < needed:
                    await interaction.followup.send(
                        embed=error_embed(f"Insufficient energy. League matches require **{needed}** ⚡ (you have **{curr_energy}**)."),
                        ephemeral=True,
                    )
                    return
            elif active_p["energy"] < 10:
                await interaction.followup.send(
                    embed=error_embed(f"Insufficient energy. Matches require **10 energy**, but you only have **{active_p['energy']}**."),
                    ephemeral=True
                )
                return

            season_threads = await resolve_season_threads(self.bot, db, interaction.guild, fixture["season_id"])
            if not season_threads:
                await interaction.followup.send(embed=error_embed("League announcement channel is not configured or threads could not be resolved."), ephemeral=True)
                return

            handler = LeagueMatchHandler(
                commentary_thread=season_threads.commentary_thread,
                fixture_id=fixture["id"],
                season_id=fixture["season_id"],
                journal_thread=season_threads.journal_thread,
                journal_standings_msg_id=season_threads.journal_standings_message_id,
            )

            await interaction.followup.send(
                embed=success_embed(
                    f"⚔️ **Match has kicked off!** Follow commentary in {season_threads.commentary_thread.mention}."
                ),
                ephemeral=True,
            )

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
            from apps.discord_bot.core.league_journal import notify_matchday_complete
            completed_md = await update_current_matchday(db, f["season_id"])
            if completed_md and interaction.guild:
                await notify_matchday_complete(self.bot, interaction.guild, db, f["season_id"], completed_md)
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
        friendly_run_id: str | None = None
        
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
                    playstyles = await fetch_playstyles(db, c["id"])
                    match_cards.append(card_from_db_row(c, playstyles))
                return match_cards, [c["id"] for c in active_cards], active_cards

            c_cards, _, _ = await get_squad_cards(challenger.id)
            o_cards, _, _ = await get_squad_cards(opponent.id)
            
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

            sim_seed = generate_sim_seed()
            run_row = await create_ephemeral_run(
                db,
                run_type="friendly",
                active_discord_id=challenger.id,
                home_discord_id=challenger.id,
                away_discord_id=opponent.id,
                sim_seed=sim_seed,
                guild_id=invitation_msg.guild.id if invitation_msg.guild else None,
                thread_id=thread.id,
            )
            friendly_run_id = run_row.get("id")
            match_rng = random.Random(sim_seed)

            # Ticker Streaming Loop
            ticker_history: list[str] = []
            key_events_list: list[dict] = []

            async for ev in stream_match(
                state, c_cards, o_cards, c_player["club_name"], o_player["club_name"], rng=match_rng
            ):
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

            # Generate Match Statistics from NSS live counters
            poss_h, poss_a, shots_h, shots_a = _match_stats_from_state(state)
            motm = state.live_stats.pick_motm(random.choice(c_cards + o_cards).name)
            box_score = {
                "possession_home": poss_h,
                "possession_away": poss_a,
                "shots_home": shots_h,
                "shots_away": shots_a,
                "motm": motm,
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
            press_embed.add_field(
                name="📐 Zone Strengths",
                value=(
                    f"{format_zone_breakdown(c_cards, c_player['club_name'])}\n"
                    f"{format_zone_breakdown(o_cards, o_player['club_name'])}"
                ),
                inline=False,
            )
            press_embed.set_footer(
                text=f"🤝 No energy spent. No coins or XP earned. {MATCH_ENGINE_FOOTER}"
            )
            
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

            # Schedule thread read-only + archive after post-match interaction window
            if thread.guild:
                asyncio.create_task(
                    archive_thread_after_delay(
                        thread,
                        thread.guild,
                        delay=MATCH_THREAD_ARCHIVE_DELAY_SEC,
                    )
                )

            if friendly_run_id:
                await complete_run(db, friendly_run_id, home_score=state.home_score, away_score=state.away_score)

        except Exception as e:
            logger.exception("Error during friendly match execution.")
            if friendly_run_id:
                await abandon_run(db, friendly_run_id)
            await thread.send(embed=error_embed(f"An error occurred during friendly match execution: {str(e)}"))
        finally:
            # Release Locks
            await db.table("match_locks").delete().in_("discord_id", [challenger.id, opponent.id]).execute()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))

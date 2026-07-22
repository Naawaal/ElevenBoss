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
    EventType,
    CommentaryEngine,
    MatchState,
    stream_match,
    collect_match_events,
    stream_match_v3,
    collect_match_events_v3,
    MatchResult,
    format_zone_breakdown,
    build_bot_match_squad,
)
from apps.discord_bot.core.match_cards import card_from_db_row, fetch_playstyles
from apps.discord_bot.core.economy_rpc import (
    sync_action_energy,
    economy_v2_enabled,
    get_match_energy_cost,
    wages_friendly_block_message,
)
from apps.discord_bot.core.league_rewards import apply_league_human_rewards
from apps.discord_bot.core.squad_validity import (
    RETIREMENT_XI_MSG,
    club_xi_block_reason,
    fetch_xi_state,
    human_club_xi_ok,
    xi_block_message,
)
from apps.discord_bot.core.match_rewards import apply_bot_match_rewards
from apps.discord_bot.core.injury_rpc import fetch_bench_ids, fetch_bench_cards, recorded_for_side
from apps.discord_bot.core.match_injury_stream import handle_injury_event
from apps.discord_bot.core.match_xp import hydrate_cards_for_match_xp
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
from apps.discord_bot.core.squad_fetch import (
    fetch_squad_xi,
    ordered_cards_to_match_squad,
    players_list_for_pitch,
)
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
    ENGINE_NSS_V3,
)
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.middleware.match_lock import acquire_match_lock, is_in_match, release_match_lock
from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.core.locks import get_guild_thread_lock
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def _ensure_thread_writable(channel: discord.abc.Messageable) -> None:
    """Force-unarchive a Discord thread (do not trust cached ``archived`` — it goes stale)."""
    if isinstance(channel, discord.Thread):
        # Always hit the API: local channel.archived is often False while Discord returns 50083
        await channel.edit(archived=False, locked=False)


async def safe_edit_message(message: discord.Message, **kwargs) -> None:
    """Edit with 429 backoff + unarchive if the stadium thread was archived mid-match."""
    for attempt in range(3):
        try:
            await message.edit(**kwargs)
            return
        except discord.HTTPException as e:
            if e.status == 429 and attempt < 2:
                await asyncio.sleep(float(getattr(e, "retry_after", 2) or 2))
                continue
            # 50083 = Thread is archived
            if getattr(e, "code", None) == 50083 and attempt < 2:
                try:
                    await _ensure_thread_writable(message.channel)
                except Exception:
                    logger.warning(
                        "Could not unarchive thread for ticker edit (channel=%s)",
                        getattr(message.channel, "id", None),
                        exc_info=True,
                    )
                    raise e
                continue
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


GOAL_SCROLL_CAP = 10

_TICKER_EMOJI: dict[str, str] = {
    "KICKOFF": "🟢",
    "HALF_TIME": "⏸️",
    "GOAL": "⚽",
    "MISS": "❌",
    "CHANCE": "🎯",
    "FOUL": "💥",
    "YELLOW_CARD": "🟨",
    "INJURY": "🩹",
    "FULL_TIME": "🏁",
    "SAVE": "🧤",
}


def format_goal_scroll_line(minute: int, actor: str) -> str:
    return f"⚽ {minute}' {actor}"


def append_goal_scroll(scroll: list[str], minute: int, actor: str) -> list[str]:
    """Append a goal line and keep at most GOAL_SCROLL_CAP (oldest drop first)."""
    scroll.append(format_goal_scroll_line(minute, actor))
    if len(scroll) > GOAL_SCROLL_CAP:
        del scroll[:-GOAL_SCROLL_CAP]
    return scroll


def format_ticker_line(ev_type: str, minute: int, text: str) -> str:
    if ev_type == "HALF_TIME":
        return "⏸️ **--- HALF TIME ---**"
    emo = _TICKER_EMOJI.get(ev_type, "⏱️")
    return f"{emo} **{minute}'** - {text}"


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
    """Live touchline — Attack/Balanced/Defend always; Wave 2 styles when v3 inbox is live."""

    _WAVE2_STYLES = (
        ("Possession", "possession", "🧠"),
        ("Counter", "counter", "⚡"),
        ("Long Ball", "long_ball", "🚀"),
        ("High Press", "high_press", "🔥"),
    )

    def __init__(
        self,
        state: MatchState,
        owner_id: int,
        *,
        inbox: Any | None = None,
        styles_enabled: bool = False,
    ) -> None:
        super().__init__(timeout=300)
        self.state = state
        self.owner_id = owner_id
        self.inbox = inbox  # DecisionInbox when engine_version=nss_v3
        if styles_enabled and inbox is not None:
            for label, key, emoji in self._WAVE2_STYLES:
                btn = discord.ui.Button(
                    style=discord.ButtonStyle.success,
                    label=f"{emoji} {label}",
                    custom_id=f"battle_touchline_style_{key}",
                    row=1,
                )
                btn.callback = self._make_style_callback(key, label)
                self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This dashboard is only for the active manager.", ephemeral=True)
            return False
        return True

    def _apply_tactic(self, tactic: str, modifier: float, momentum: float) -> None:
        if self.inbox is not None:
            from match_engine.v3 import DecisionIntent

            self.inbox.push(
                DecisionIntent(
                    side="home",
                    kind="set_tactic",
                    payload={"tactic": tactic, "stance_modifier": modifier},
                    requested_at_minute=int(getattr(self.state, "minute", 0) or 0),
                    source="human",
                )
            )
            # Optimistic UI + momentum (generator reads pending_home_momentum on shared state)
            self.state.home_tactics_modifier = modifier
            self.state.pending_home_momentum = momentum
            if hasattr(self.state, "transition_style"):
                self.state.transition_style = tactic
        else:
            self.state.home_tactics_modifier = modifier
            self.state.pending_home_momentum = momentum

    def _make_style_callback(self, style_key: str, label: str):
        async def _cb(interaction: discord.Interaction) -> None:
            from match_engine.v3.tactics import get_transition_profile

            prof = get_transition_profile(style_key)
            self._apply_tactic(style_key, float(prof.stance_modifier), 0.0)
            await interaction.response.send_message(
                f"📣 **Touchline**: Style set to **{label}** "
                f"(applies at the next Decision Window).",
                ephemeral=True,
            )

        return _cb

    @discord.ui.button(style=discord.ButtonStyle.danger, label="⚔️ Attack", custom_id="battle_touchline_attack", row=0)
    async def attack_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._apply_tactic("attack", 1.3, 5.0)
        await interaction.response.send_message("📣 **Touchline**: Tactical focus shifted to **Attack**!", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⚖️ Balanced", custom_id="battle_touchline_balanced", row=0)
    async def balanced_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._apply_tactic("balanced", 1.0, 0.0)
        await interaction.response.send_message("📣 **Touchline**: Tactics set to **Balanced** shape.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🛡️ Defend", custom_id="battle_touchline_defend", row=0)
    async def defend_callback(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._apply_tactic("defend", 0.7, -5.0)
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
    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None, energy_cost: int | None = None, fatigue_warning: str | None = None) -> discord.abc.Messageable:
        """Post initial ticket, optional thread, and return the target channel/thread for posting commentary."""
        pass

    @abc.abstractmethod
    async def start_match(self, target: discord.abc.Messageable, home_name: str, away_name: str, touchline_view: discord.ui.View | None) -> None:
        """Send the initial match scoreboard/momentum/commentary state."""
        pass

    @abc.abstractmethod
    async def update_ticker(
        self,
        ev: dict,
        state: MatchState,
        recent_ticker: list[str],
        touchline_view: discord.ui.View | None,
        goal_scroll: list[str] | None = None,
    ) -> None:
        """Update scoreboard / Goal Scroll / momentum / commentary for a match tick."""
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

    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None, energy_cost: int | None = None, fatigue_warning: str | None = None) -> discord.abc.Messageable:
        if not interaction:
            raise ValueError("StandardMatchHandler requires an active interaction context.")

        desc = "A new match has kicked off! Live commentary is streaming now."
        if fatigue_warning:
            desc = f"{desc}\n\n{fatigue_warning}"

        ticket_embed = discord.Embed(
            title=f"🎫 Match Ticket: {home_name} vs {away_name}",
            description=desc,
            color=0x00FF87
        )
        if matchday:
            ticket_embed.add_field(name="Matchday", value=f"Matchday {matchday}", inline=True)

        if energy_cost is not None and energy_cost > 0:
            ticket_embed.add_field(name="Cost", value=f"⚡ **{energy_cost}** Action Energy", inline=True)
        elif energy_cost == 0:
            ticket_embed.add_field(name="Cost", value="Free Match", inline=True)
        else:
            ticket_embed.add_field(name="Cost", value="⚡ Energy cost applies", inline=True)

        channel = interaction.channel
        # Always ticket + spawn from the parent text channel — never reuse an old stadium
        # thread (leftover archive_thread_after_delay tasks re-archive mid-match → 50083).
        ticket_dest: discord.abc.Messageable = channel
        if isinstance(channel, discord.Thread) and channel.parent is not None:
            ticket_dest = channel.parent

        # Prefer parent channel send (works after defer); avoids posting into archived threads
        self.ticket_msg = await ticket_dest.send(embed=ticket_embed)

        self.thread = None
        if (
            not self.league_mode
            and interaction.guild
            and hasattr(ticket_dest, "create_thread")
            and not isinstance(ticket_dest, discord.Thread)
        ):
            try:
                self.thread = await ticket_dest.create_thread(
                    name=f"🏟️ {home_name} vs {away_name} - Live",
                    message=self.ticket_msg,
                    auto_archive_duration=1440,  # 24h — live matches outlast 60m idle archive
                )
            except Exception as e:
                logger.warning(f"Failed to create public match thread: {e}. Falling back to main channel.")

        if self.thread:
            ticket_embed.add_field(name="Stadium Thread", value=self.thread.mention, inline=False)
            await safe_edit_message(self.ticket_msg, embed=ticket_embed)

        return self.thread if self.thread else ticket_dest

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

    async def update_ticker(
        self,
        ev: dict,
        state: MatchState,
        recent_ticker: list[str],
        touchline_view: discord.ui.View | None,
        goal_scroll: list[str] | None = None,
    ) -> None:
        embed = discord.Embed(
            title=f"🏟️ Live Stadium: {self.home_name or 'Home'} vs {self.away_name or 'Away'}",
            color=0x00FF87
        )
        embed.add_field(name="Scoreboard", value=f"🏟️ **{self.home_name or 'Home'}** `{ev['score_update']}` **{self.away_name or 'Away'}**", inline=False)
        if goal_scroll:
            embed.add_field(name="Goal Scroll", value="\n".join(goal_scroll), inline=False)
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
                xp_line=(kwargs.get("fitness_summary") or {}).get("xp_line"),
            )
        else:
            rewards_value = f"🪙 **+{active_earned} coins**"
            xp_line = (kwargs.get("fitness_summary") or {}).get("xp_line")
            if xp_line:
                rewards_value += f"\n{xp_line}"
            if active_pts > 0:
                rewards_value += f"\n📊 **+{active_pts} Division Rank**"

        press_embed.add_field(
            name="🎁 Rewards",
            value=rewards_value,
            inline=True
        )
        fitness_line = (kwargs.get("fitness_summary") or {}).get("line")
        if fitness_line:
            press_embed.add_field(name="💪 Fitness", value=fitness_line, inline=False)
        explanation = kwargs.get("explanation")
        if explanation:
            tips = explanation.get("turning_points") or []
            lines = [explanation.get("headline") or "Key moments"]
            for tp in tips[:3]:
                lines.append(f"• {tp.get('minute', '?')}' — {tp.get('type', 'moment')}")
            press_embed.add_field(
                name="🔍 How it was decided",
                value="\n".join(lines)[:1024],
                inline=False,
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
        *,
        home_formation: str = "4-4-2",
        away_formation: str = "4-4-2",
        home_assignments: dict[int, dict] | None = None,
        away_assignments: dict[int, dict] | None = None,
    ) -> None:
        """Post pitch images for both XIs before kickoff."""
        try:
            home_pitch_list = (
                players_list_for_pitch(home_formation, home_assignments)
                if home_assignments
                else home_cards[:11]
            )
            home_pitch = await generate_squad_pitch(home_formation, home_pitch_list)
            await self.commentary_thread.send(content=f"📋 **{home_name}** — Starting XI (`{home_formation}`)", file=home_pitch)
            if away_cards:
                away_pitch_list = (
                    players_list_for_pitch(away_formation, away_assignments)
                    if away_assignments
                    else away_cards[:11]
                )
                away_pitch = await generate_squad_pitch(away_formation, away_pitch_list)
                await self.commentary_thread.send(
                    content=f"📋 **{away_name}** — Starting XI (`{away_formation}`)",
                    file=away_pitch,
                )
        except Exception:
            logger.debug("Prematch pitch render skipped", exc_info=True)

    async def initialize(self, interaction: discord.Interaction | None, home_name: str, away_name: str, matchday: int = None, energy_cost: int | None = None, fatigue_warning: str | None = None) -> discord.abc.Messageable:
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

    async def update_ticker(
        self,
        ev: dict,
        state: MatchState,
        recent_ticker: list[str],
        touchline_view: discord.ui.View | None,
        goal_scroll: list[str] | None = None,
    ) -> None:
        embed = discord.Embed(
            title=f"🏟️ Live League Match: {self.home_name or 'Home'} vs {self.away_name or 'Away'}",
            color=0x00FF87
        )
        embed.add_field(name="Scoreboard", value=f"🏟️ **{self.home_name or 'Home'}** `{ev['score_update']}` **{self.away_name or 'Away'}**", inline=False)
        if goal_scroll:
            embed.add_field(name="Goal Scroll", value="\n".join(goal_scroll), inline=False)
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

        fitness_line = (kwargs.get("fitness_summary") or {}).get("line")
        if fitness_line:
            press_embed.add_field(name="💪 Fitness", value=fitness_line, inline=False)

        explanation = kwargs.get("explanation")
        if explanation:
            tips = explanation.get("turning_points") or []
            lines = [explanation.get("headline") or "Key moments"]
            for tp in tips[:3]:
                lines.append(f"• {tp.get('minute', '?')}' — {tp.get('type', 'moment')}")
            press_embed.add_field(
                name="🔍 How it was decided",
                value="\n".join(lines)[:1024],
                inline=False,
            )

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
    skip_xi_gate: bool = False,
    home_card_ids: list[str] | None = None,
    away_card_ids: list[str] | None = None,
) -> None:
    home_p = fixture["home"]
    away_p = fixture["away"]
    fixture_id = fixture["id"]

    # Skip if already played — on recovery avoids wiping resolved_by / re-settling.
    if fixture.get("is_played"):
        logger.info(
            "Fixture %s already played; skipping %s.",
            fixture_id,
            "recovery" if recovery else "simulation",
        )
        return

    home_squad: list[MatchPlayerCard] = []
    home_rating = 60.0
    home_cards: list[dict] = []
    home_formation = "4-4-2"
    home_assignments: dict[int, dict] = {}
    away_squad: list[MatchPlayerCard] = []
    away_rating = 60.0
    away_cards: list[dict] = []
    away_formation = "4-4-2"
    away_assignments: dict[int, dict] = {}

    sim_seed = sim_seed if sim_seed is not None else generate_sim_seed()
    match_rng = random.Random(sim_seed)
    bot_squad_rng = random.Random(sim_seed ^ 0xB075AD)
    engine_version = "nss_v2"

    if recovery and run_id:
        run_res = await db.table("match_runs").select(
            "squad_snapshot,engine_version"
        ).eq("id", run_id).maybe_single().execute()
        snapshot = (run_res.data or {}).get("squad_snapshot") or {}
        engine_version = (run_res.data or {}).get("engine_version") or "nss_v2"
        home_squad, away_squad = squads_from_snapshot(snapshot)
        home_rating = float(snapshot.get("home_rating", 60.0))
        away_rating = float(snapshot.get("away_rating", 60.0))
        home_name = snapshot.get("home_name", home_p["club_name"])
        away_name = snapshot.get("away_name", away_p["club_name"])
        home_card_ids = snapshot.get("home_card_ids", [])
        away_card_ids = snapshot.get("away_card_ids", [])
        home_formation = snapshot.get("home_formation", "4-4-2")
        away_formation = snapshot.get("away_formation", "4-4-2")
        # Recovery snapshots only store ids — hydrate name/age for match XP (FR-001/002)
        home_cards = await hydrate_cards_for_match_xp(db, home_card_ids) if not home_p["is_ai"] else []
        away_cards = await hydrate_cards_for_match_xp(db, away_card_ids) if not away_p["is_ai"] else []
    else:
        if home_p["is_ai"]:
            home_rating = float(home_p.get("ai_rating") or 60.0)
            home_squad = build_bot_match_squad(int(home_rating), bot_squad_rng)
        elif home_card_ids:
            home_cards = await hydrate_cards_for_match_xp(db, home_card_ids)
            home_formation, home_assignments, _ = await fetch_squad_xi(
                db, int(fixture["home_team_id"])
            )
            home_squad = await ordered_cards_to_match_squad(db, home_cards)
            if home_squad:
                home_rating = sum(p.overall for p in home_squad) / len(home_squad)
        else:
            home_formation, home_assignments, home_cards = await fetch_squad_xi(
                db, int(fixture["home_team_id"])
            )
            home_squad = await ordered_cards_to_match_squad(db, home_cards)
            if home_squad:
                home_rating = sum(p.overall for p in home_squad) / len(home_squad)

        if away_p["is_ai"]:
            away_rating = float(away_p.get("ai_rating") or 60.0)
            away_squad = build_bot_match_squad(int(away_rating), bot_squad_rng)
        elif away_card_ids:
            away_cards = await hydrate_cards_for_match_xp(db, away_card_ids)
            away_formation, away_assignments, _ = await fetch_squad_xi(
                db, int(fixture["away_team_id"])
            )
            away_squad = await ordered_cards_to_match_squad(db, away_cards)
            if away_squad:
                away_rating = sum(p.overall for p in away_squad) / len(away_squad)
        else:
            away_formation, away_assignments, away_cards = await fetch_squad_xi(
                db, int(fixture["away_team_id"])
            )
            away_squad = await ordered_cards_to_match_squad(db, away_cards)
            if away_squad:
                away_rating = sum(p.overall for p in away_squad) / len(away_squad)

        home_name = home_p["club_name"] + (" (AI)" if home_p["is_ai"] else "")
        away_name = away_p["club_name"] + (" (AI)" if away_p["is_ai"] else "")

        # Fail closed: human clubs with retirement holes / incomplete XI must not auto-sim
        if (
            not skip_xi_gate
            and not home_p["is_ai"]
            and not await human_club_xi_ok(
                db, int(fixture["home_team_id"]), card_count=len(home_cards)
            )
        ):
            logger.warning(
                "Skipping fixture %s: home club %s has invalid/incomplete XI (squad_invalid or count!=11).",
                fixture_id,
                fixture["home_team_id"],
            )
            if not silent and active_player_id and active_player_id == int(fixture["home_team_id"]):
                try:
                    msg = await club_xi_block_reason(db, active_player_id) or RETIREMENT_XI_MSG
                    user = await bot.fetch_user(active_player_id)
                    await user.send(embed=error_embed(msg))
                except Exception:
                    pass
            return
        if (
            not skip_xi_gate
            and not away_p["is_ai"]
            and not await human_club_xi_ok(
                db, int(fixture["away_team_id"]), card_count=len(away_cards)
            )
        ):
            logger.warning(
                "Skipping fixture %s: away club %s has invalid/incomplete XI (squad_invalid or count!=11).",
                fixture_id,
                fixture["away_team_id"],
            )
            if not silent and active_player_id and active_player_id == int(fixture["away_team_id"]):
                try:
                    msg = await club_xi_block_reason(db, active_player_id) or RETIREMENT_XI_MSG
                    user = await bot.fetch_user(active_player_id)
                    await user.send(embed=error_embed(msg))
                except Exception:
                    pass
            return

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
                home_formation=home_formation,
                away_formation=away_formation,
            ),
            guild_id=guild.id if guild else None,
            thread_id=thread_id,
            home_discord_id=int(fixture["home_team_id"]),
            away_discord_id=int(fixture["away_team_id"]),
        )
        run_id = run_row.get("id", run_id)
        engine_version = run_row.get("engine_version") or engine_version

    state = MatchState(home_rating=home_rating, away_rating=away_rating)
    state.injuries_enabled = True
    # Sim injury rolls: prefer active human's intensity; each side still persists own tier.
    # auto_sim passes active_player_id=None — do not int(None).
    if active_player_id is not None:
        active_row = (
            home_p
            if int(home_p.get("discord_id") or 0) == int(active_player_id)
            else away_p
        )
    else:
        active_row = home_p if not home_p.get("is_ai") else away_p
    if active_row.get("is_ai"):
        active_row = home_p if not home_p.get("is_ai") else away_p
    state.intensity_tier = int(active_row.get("intensity_tier") or 1)
    interactive: list[str] = []
    if not home_p["is_ai"]:
        interactive.append("home")
        state.bench_home = await fetch_bench_cards(
            db, int(fixture["home_team_id"]), [str(c["id"]) for c in home_cards]
        )
    if not away_p["is_ai"]:
        interactive.append("away")
        state.bench_away = await fetch_bench_cards(
            db, int(fixture["away_team_id"]), [str(c["id"]) for c in away_cards]
        )
    if not silent:
        state.interactive_sides = interactive
    else:
        state.interactive_sides = []

    commentary_engine = CommentaryEngine()
    target = await handler.initialize(None, home_name, away_name, fixture["matchday"])

    touchline_user_id = active_player_id if active_player_id else 0
    touchline_inbox = None
    if engine_version == ENGINE_NSS_V3 and touchline_user_id and not silent:
        from match_engine.v3 import DecisionInbox

        touchline_inbox = DecisionInbox()
    touchline_view = (
        TouchlineView(
            state,
            touchline_user_id,
            inbox=touchline_inbox,
            styles_enabled=touchline_inbox is not None,
        )
        if touchline_user_id and not silent
        else None
    )

    owner_by_side = {}
    if not home_p["is_ai"]:
        owner_by_side["home"] = int(fixture["home_team_id"])
    if not away_p["is_ai"]:
        owner_by_side["away"] = int(fixture["away_team_id"])

    if not silent:
        if hasattr(handler, "post_prematch_lineups") and (home_cards or away_cards):
            await handler.post_prematch_lineups(
                home_name,
                away_name,
                home_cards,
                away_cards,
                home_formation=home_formation,
                away_formation=away_formation,
                home_assignments=home_assignments or None,
                away_assignments=away_assignments or None,
            )
        await handler.start_match(target, home_name, away_name, touchline_view)

    ticker_history: list[str] = []
    goal_scroll: list[str] = []
    key_events_list: list[dict] = []

    async def _consume_event(ev: dict) -> None:
        variables = {"actor": ev["actor"], "team": ev["team"]}
        comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
        text = comm["text"]
        urgency = comm["urgency"]
        injury_note = await handle_injury_event(
            ev=ev,
            state=state,
            channel=getattr(handler, "commentary_thread", None) or target,
            home_squad=home_squad,
            away_squad=away_squad,
            owner_by_side=owner_by_side,
            silent=False,
        )
        if injury_note:
            text = f"{text} {injury_note}"
        ticker_history.append(format_ticker_line(ev["type"], ev["minute"], text))
        if ev["type"] == "GOAL":
            append_goal_scroll(goal_scroll, ev["minute"], ev["actor"])
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
            await handler.update_ticker(
                ev, state, ticker_history[-5:], touchline_view, goal_scroll=goal_scroll
            )
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
        recovery_decisions = None
        if engine_version == ENGINE_NSS_V3 and recovery and run_id:
            from apps.discord_bot.core.match_events_store import load_run_decision_intents

            recovery_decisions = await load_run_decision_intents(db, run_id)
        if engine_version == ENGINE_NSS_V3:
            state, events, _canon = await collect_match_events_v3(
                state,
                home_squad,
                away_squad,
                home_name,
                away_name,
                sim_seed,
                decisions=recovery_decisions or None,
            )
            if run_id:
                from apps.discord_bot.core.match_events_store import append_match_events

                await append_match_events(db, run_id, _canon, flushed_thru=0)
        else:
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
        event_stream = (
            stream_match_v3(
                state,
                home_squad,
                away_squad,
                home_name,
                away_name,
                sim_seed=sim_seed,
                inbox=touchline_inbox,
            )
            if engine_version == ENGINE_NSS_V3
            else stream_match(
                state, home_squad, away_squad, home_name, away_name, rng=match_rng
            )
        )
        async for ev in event_stream:
            await _consume_event(ev)
        if engine_version == ENGINE_NSS_V3 and run_id:
            from apps.discord_bot.core.match_events_store import append_match_events

            live_canon = list(getattr(state, "_nss_v3_events", []) or [])
            if live_canon:
                await append_match_events(db, run_id, live_canon, flushed_thru=0)

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
    h_fitness: dict = {}
    a_fitness: dict = {}

    if not home_p["is_ai"]:
        h_bench = await fetch_bench_ids(
            db, int(fixture["home_team_id"]), [str(c["id"]) for c in home_cards]
        )
        h_coins, h_pts, h_fitness = await apply_league_human_rewards(
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
            bench_ids=h_bench,
            tactics_modifier=float(getattr(state, "home_tactics_modifier", 1.0) or 1.0),
            bot=bot,
            recorded_injuries=recorded_for_side(state.recorded_injuries, "home"),
        )
        from apps.discord_bot.core.league_rewards import check_matchday_milestone
        h_milestone = await check_matchday_milestone(
            db, player_id=int(fixture["home_team_id"]), season_id=fixture["season_id"],
            matchday=fixture["matchday"], points_earned=h_pts,
        )

    if not away_p["is_ai"]:
        a_bench = await fetch_bench_ids(
            db, int(fixture["away_team_id"]), [str(c["id"]) for c in away_cards]
        )
        a_coins, a_pts, a_fitness = await apply_league_human_rewards(
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
            bench_ids=a_bench,
            tactics_modifier=1.0,
            bot=bot,
            recorded_injuries=recorded_for_side(state.recorded_injuries, "away"),
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
        "played_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": "manual" if active_player_id else "auto_sim",
        "result_type": "settled",
        "status": "settled",
        "match_seed": str(sim_seed),
        "engine_version": "v1",
    }).eq("id", fixture_id).eq("is_played", False).execute()

    # Durable settle before Discord present (US-42.4) — never abandon-after-pay
    if run_id:
        await complete_run(db, run_id, home_score=state.home_score, away_score=state.away_score)

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

    explanation_kw: dict = {}
    if engine_version == ENGINE_NSS_V3:
        from match_engine.v3 import project_explanation

        v3_events = list(getattr(state, "_nss_v3_events", []) or [])
        if v3_events:
            league_res = (
                "win"
                if state.home_score > state.away_score
                else ("loss" if state.home_score < state.away_score else "draw")
            )
            expl = project_explanation(v3_events, result=league_res)
            explanation_kw["explanation"] = {
                "headline": expl.headline,
                "turning_points": expl.turning_points,
                "primary_turning_seq": expl.primary_turning_seq,
            }

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
        fitness_summary=(
            h_fitness if active_player_id == fixture["home_team_id"] else a_fitness
        ),
        **explanation_kw,
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

    @discord.ui.button(style=discord.ButtonStyle.danger, label="🤖 Bot Battle ⚡", custom_id="arena_bot_battle")
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

        v2 = await economy_v2_enabled(db)
        bot_energy = await get_match_energy_cost(db, "bot", v2=v2)

        embed = discord.Embed(
            title="🏟️ ElevenBoss Battle Arena",
            description=(
                f"Welcome to the Battle Arena, Manager **{player['manager_name']}**!\n"
                f"Choose your competitive match pathway below. Bot battles consume **{bot_energy}** ⚡ action energy.\n"
                f"Friendly matches are **free** — no energy, no coins, no XP."
            ),
            color=0x00FF87
        )
        embed.set_footer(text="⚡ Energy cost applies")
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

        wage_msg = await wages_friendly_block_message(db, challenger.id)
        if wage_msg:
            await interaction.followup.send(embed=error_embed(wage_msg), ephemeral=True)
            return

        # Check if opponent is registered
        opp_res = await db.table("players").select("*").eq("discord_id", opponent.id).maybe_single().execute()
        opp_player = opp_res.data if opp_res else None
        if not opp_player:
            await interaction.followup.send(embed=error_embed(f"The manager {opponent.display_name} is not registered yet!"), ephemeral=True)
            return

        opp_wage = await wages_friendly_block_message(db, opponent.id)
        if opp_wage:
            await interaction.followup.send(
                embed=error_embed(f"{opponent.display_name} cannot play friendlies: {opp_wage}"),
                ephemeral=True,
            )
            return

        # Check if either player is already locked in a match
        challenger_locked = await is_in_match(db, challenger.id)
        opponent_locked = await is_in_match(db, opponent.id)
        if challenger_locked or opponent_locked:
            if challenger_locked and opponent_locked:
                msg = "Both you and the opponent are currently locked in another match."
            elif challenger_locked:
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
        rewards_applied = False
        settled = False
        state = None
        try:
            db = await get_client()

            if not await acquire_match_lock(db, interaction.user.id, "bot"):
                await interaction.followup.send(embed=error_embed("You are currently locked in another match."), ephemeral=True)
                return
            lock_acquired = True

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
            needed = await get_match_energy_cost(db, "bot", v2=v2)
            if curr_energy < needed:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Insufficient energy. Bot matches require **{needed}** ⚡ (you have **{curr_energy}**)."
                    ),
                    ephemeral=True,
                )
                return

            # 3. Fetch starting 11 details (slot-ordered + saved formation)
            _, _, active_cards = await fetch_squad_xi(db, interaction.user.id)
            count = len(active_cards)
            _, squad_invalid = await fetch_xi_state(db, interaction.user.id)
            block = await club_xi_block_reason(db, interaction.user.id, card_count=count)
            if block:
                await interaction.followup.send(embed=error_embed(block), ephemeral=True)
                return

            injured = [c["name"] for c in active_cards if c.get("injury_tier")]
            if injured:
                await interaction.followup.send(
                    embed=error_embed(
                        "Injured players cannot start. Replace them in `/squad`:\n"
                        + ", ".join(f"**{n}**" for n in injured[:5])
                    ),
                    ephemeral=True,
                )
                return
 
            # 4. Construct MatchPlayerCard models including morale-adjusted OVR
            match_cards = await ordered_cards_to_match_squad(db, active_cards)
 
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
            state.injuries_enabled = True
            state.interactive_sides = ["home"]
            state.intensity_tier = int(player.get("intensity_tier") or 1)
            state.bench_home = await fetch_bench_cards(
                db, interaction.user.id, [str(c["id"]) for c in active_cards]
            )
            commentary_engine = CommentaryEngine()

            # Instantiate StandardMatchHandler
            handler = StandardMatchHandler(self.bot, league_mode=False)

            from player_engine import count_heavily_fatigued

            heavy_n = count_heavily_fatigued(active_cards)
            fatigue_warning = None
            if heavy_n > 0:
                fatigue_warning = (
                    f"⚠️ Warning: **{heavy_n}** players are heavily fatigued. "
                    "High risk of injury."
                )

            # Initialize target channel
            target = await handler.initialize(
                interaction,
                player["club_name"],
                opp_name,
                energy_cost=needed,
                fatigue_warning=fatigue_warning,
            )

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
            engine_version = run_row.get("engine_version") or "nss_v2"

            touchline_inbox = None
            if engine_version == ENGINE_NSS_V3:
                from match_engine.v3 import DecisionInbox

                touchline_inbox = DecisionInbox()
            touchline_view = TouchlineView(
                state,
                interaction.user.id,
                inbox=touchline_inbox,
                styles_enabled=touchline_inbox is not None,
            )
            await handler.start_match(target, player["club_name"], opp_name, touchline_view)

            match_rng = random.Random(sim_seed)
            opp_squad = build_bot_match_squad(int(opp_rating), random.Random(sim_seed ^ 0xB075AD))
            # Commentary Streaming Loop
            ticker_history: list[str] = []
            goal_scroll: list[str] = []
            key_events_list: list[dict] = []
            owner_by_side = {"home": interaction.user.id}
            injury_channel = getattr(handler, "thread", None) or target

            bot_stream = (
                stream_match_v3(
                    state,
                    match_cards,
                    opp_squad,
                    player["club_name"],
                    opp_name,
                    sim_seed=sim_seed,
                    inbox=touchline_inbox,
                )
                if engine_version == ENGINE_NSS_V3
                else stream_match(
                    state, match_cards, opp_squad, player["club_name"], opp_name, rng=match_rng
                )
            )
            async for ev in bot_stream:
                variables = {
                    "actor": ev["actor"],
                    "team": ev["team"]
                }
                comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
                text = comm["text"]
                urgency = comm["urgency"]

                injury_note = await handle_injury_event(
                    ev=ev,
                    state=state,
                    channel=injury_channel,
                    home_squad=match_cards,
                    away_squad=opp_squad,
                    owner_by_side=owner_by_side,
                    silent=False,
                )
                if injury_note:
                    text = f"{text} {injury_note}"

                ticker_history.append(format_ticker_line(ev["type"], ev["minute"], text))
                if ev["type"] == "GOAL":
                    append_goal_scroll(goal_scroll, ev["minute"], ev["actor"])
                recent_ticker = ticker_history[-5:]

                await handler.update_ticker(
                    ev, state, recent_ticker, touchline_view, goal_scroll=goal_scroll
                )

                if ev["type"] in ["KICKOFF", "HALF_TIME", "GOAL", "MISS", "CHANCE", "FOUL", "INJURY", "FULL_TIME"]:
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

            if engine_version == ENGINE_NSS_V3 and bot_run_id:
                from apps.discord_bot.core.match_events_store import append_match_events

                bot_canon = list(getattr(state, "_nss_v3_events", []) or [])
                if bot_canon:
                    await append_match_events(db, bot_run_id, bot_canon, flushed_thru=0)

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

            coins_earned, fitness_summary = await apply_bot_match_rewards(
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
                bench_ids=await fetch_bench_ids(
                    db, interaction.user.id, [str(c["id"]) for c in active_cards]
                ),
                tactics_modifier=float(getattr(state, "home_tactics_modifier", 1.0) or 1.0),
                bot=self.bot,
                recorded_injuries=recorded_for_side(state.recorded_injuries, "home"),
            )
            rewards_applied = True

            # Durable settle before Discord present (US-42.4)
            if bot_run_id:
                await complete_run(db, bot_run_id, home_score=state.home_score, away_score=state.away_score)
                settled = True

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

            explanation_kw: dict = {}
            if engine_version == ENGINE_NSS_V3:
                from match_engine.v3 import project_explanation

                v3_events = list(getattr(state, "_nss_v3_events", []) or [])
                if v3_events:
                    expl = project_explanation(v3_events, result=res_str)
                    explanation_kw["explanation"] = {
                        "headline": expl.headline,
                        "turning_points": expl.turning_points,
                        "primary_turning_seq": expl.primary_turning_seq,
                    }

            try:
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
                    fitness_summary=fitness_summary,
                    **explanation_kw,
                )
            except Exception:
                # Present-retry only — rewards already durable; never abandon-after-pay
                logger.exception(
                    "Bot match present failed after settle (run=%s); rewards kept.",
                    bot_run_id,
                )
                if interaction.response.is_done():
                    await interaction.followup.send(
                        embed=error_embed(
                            "Match result was saved, but the summary failed to post. "
                            "Your rewards are safe — check `/development` if needed."
                        ),
                        ephemeral=True,
                    )
        except Exception as e:
            logger.exception("Failed to simulate match.")
            if bot_run_id and not settled:
                if rewards_applied:
                    try:
                        await complete_run(
                            db, bot_run_id,
                            home_score=state.home_score if state else 0,
                            away_score=state.away_score if state else 0,
                        )
                    except Exception:
                        logger.exception("complete_run after partial rewards failed for %s", bot_run_id)
                else:
                    await abandon_run(db, bot_run_id, reason="bot_sim_failed")
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed(api_error_message(e)), ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed(api_error_message(e)), ephemeral=True)
        finally:
            if lock_acquired:
                await release_match_lock(db, interaction.user.id)

    async def execute_league_match(self, interaction: discord.Interaction, fixture: dict) -> None:
        locks_held: list[int] = []
        fixture_id: str | None = None
        db = await get_client()
        user_id = interaction.user.id
        try:
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
                await interaction.followup.send(
                    embed=error_embed(
                        "Season is paused. Matchdays are frozen until the server is available again "
                        "(windows will extend when play resumes)."
                    ),
                    ephemeral=True,
                )
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

            # 11-player XI guard (+ retirement invalid flag)
            xi_count, squad_invalid = await fetch_xi_state(db, user_id)
            block = await club_xi_block_reason(db, user_id, card_count=xi_count)
            if block:
                await interaction.followup.send(embed=error_embed(block), ephemeral=True)
                return

            v2 = await economy_v2_enabled(db)
            if v2:
                energy_row = await sync_action_energy(db, user_id)
                curr_energy = energy_row.get("action_energy", active_p.get("action_energy", 0))
                needed = await get_match_energy_cost(db, "league", v2=True)
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

            # Lock both human clubs after eligibility (parity with league_lifecycle_engine)
            for club_id, is_ai in (
                (int(f["home_team_id"]), bool(f["home"].get("is_ai"))),
                (int(f["away_team_id"]), bool(f["away"].get("is_ai"))),
            ):
                if is_ai:
                    continue
                if not await acquire_match_lock(db, club_id, "league"):
                    await interaction.followup.send(
                        embed=error_embed("You or your opponent are currently locked in another match."),
                        ephemeral=True,
                    )
                    return
                locks_held.append(club_id)

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
            completed_md = await update_current_matchday(db, f["season_id"], bot=self.bot)
            if completed_md and interaction.guild:
                await notify_matchday_complete(self.bot, interaction.guild, db, f["season_id"], completed_md)
        except Exception as e:
            logger.exception("Failed to execute league match.")
            if fixture_id:
                active = await get_active_fixture_run(db, fixture_id)
                if active:
                    try:
                        await abandon_run(db, active["id"], reason="league_play_failed")
                    except Exception:
                        logger.exception("abandon_match_run failed for fixture %s", fixture_id)
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed(api_error_message(e)), ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed(api_error_message(e)), ephemeral=True)
        finally:
            for held_id in locks_held:
                await release_match_lock(db, held_id)

    async def start_friendly_match(
        self,
        interaction: discord.Interaction,
        challenger: discord.Member | discord.User,
        opponent: discord.Member,
        invitation_msg: discord.Message
    ) -> None:
        db = await get_client()
        friendly_run_id: str | None = None
        locks_held: list[int] = []

        if await is_in_match(db, challenger.id) or await is_in_match(db, opponent.id):
            await invitation_msg.channel.send(
                embed=error_embed("One or both managers are already in another match."),
            )
            return

        c_res = await db.table("players").select("*").eq("discord_id", challenger.id).maybe_single().execute()
        o_res = await db.table("players").select("*").eq("discord_id", opponent.id).maybe_single().execute()
        c_player = c_res.data if c_res else None
        o_player = o_res.data if o_res else None
        if not c_player or not o_player:
            await invitation_msg.channel.send(embed=error_embed("One or both managers are not registered."))
            return

        c_block = await club_xi_block_reason(db, challenger.id)
        o_block = await club_xi_block_reason(db, opponent.id)
        if c_block or o_block:
            parts = []
            if c_block:
                parts.append(f"**{c_player['manager_name']}**: {c_block}")
            if o_block:
                parts.append(f"**{o_player['manager_name']}**: {o_block}")
            await invitation_msg.channel.send(
                embed=error_embed("Friendly match cancelled:\n" + "\n".join(parts))
            )
            return

        for mgr_id, mgr_name in (
            (challenger.id, c_player["manager_name"]),
            (opponent.id, o_player["manager_name"]),
        ):
            wage_msg = await wages_friendly_block_message(db, mgr_id)
            if wage_msg:
                await invitation_msg.channel.send(
                    embed=error_embed(f"**{mgr_name}**: {wage_msg}")
                )
                return

        # 1. Spawning Thread
        thread = None
        try:
            thread_name = f"🤝 {c_player['club_name']} vs {o_player['club_name']} – Friendly"
            thread = await invitation_msg.create_thread(
                name=thread_name,
                auto_archive_duration=60
            )
        except Exception as e:
            logger.exception("Failed to spawn friendly match thread.")
            await invitation_msg.channel.send(embed=error_embed(f"Failed to create match thread: {str(e)}"))
            return

        # 2. Acquire concurrency locks
        if not await acquire_match_lock(db, challenger.id, "friendly"):
            await thread.send(embed=error_embed("Could not acquire match lock for challenger."))
            return
        locks_held.append(challenger.id)
        if not await acquire_match_lock(db, opponent.id, "friendly"):
            await release_match_lock(db, challenger.id)
            await thread.send(embed=error_embed("Could not acquire match lock for opponent."))
            return
        locks_held.append(opponent.id)

        try:
            async def get_squad_cards(discord_id: int):
                _, assignments, active_cards = await fetch_squad_xi(db, discord_id)
                match_cards = await ordered_cards_to_match_squad(db, active_cards)
                return match_cards, [c["id"] for c in active_cards], active_cards, assignments

            c_cards, _, _, _ = await get_squad_cards(challenger.id)
            o_cards, _, _, _ = await get_squad_cards(opponent.id)

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
            engine_version = run_row.get("engine_version") or "nss_v2"
            match_rng = random.Random(sim_seed)

            # Ticker Streaming Loop
            ticker_history: list[str] = []
            goal_scroll: list[str] = []
            key_events_list: list[dict] = []

            # Friendly remains sandbox — no match_events flush even on v3
            friendly_stream = (
                stream_match_v3(
                    state,
                    c_cards,
                    o_cards,
                    c_player["club_name"],
                    o_player["club_name"],
                    sim_seed=sim_seed,
                )
                if engine_version == ENGINE_NSS_V3
                else stream_match(
                    state,
                    c_cards,
                    o_cards,
                    c_player["club_name"],
                    o_player["club_name"],
                    rng=match_rng,
                )
            )
            async for ev in friendly_stream:
                variables = {
                    "actor": ev["actor"],
                    "team": ev["team"]
                }
                comm = commentary_engine.get_commentary(ev["type"], state.context_tags, variables)
                text = comm["text"]
                urgency = comm["urgency"]

                ticker_history.append(format_ticker_line(ev["type"], ev["minute"], text))
                if ev["type"] == "GOAL":
                    append_goal_scroll(goal_scroll, ev["minute"], ev["actor"])
                recent_ticker = ticker_history[-5:]

                embed = discord.Embed(
                    title=f"🏟️ Live Friendly Match: {c_player['club_name']} vs {o_player['club_name']}",
                    color=0x00FF87
                )
                embed.add_field(name="Scoreboard", value=f"🏟️ **{c_player['club_name']}** `{ev['score_update']}` **{o_player['club_name']}**", inline=False)
                if goal_scroll:
                    embed.add_field(name="Goal Scroll", value="\n".join(goal_scroll), inline=False)
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
            await thread.send(embed=error_embed(api_error_message(e)))
        finally:
            for uid in locks_held:
                await release_match_lock(db, uid)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))

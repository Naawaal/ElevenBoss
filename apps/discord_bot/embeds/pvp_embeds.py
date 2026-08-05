# apps/discord_bot/embeds/pvp_embeds.py
"""Ranked PvP, Ghost Backfill, and Practice embeds (Features 053 & 054)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import discord

from pvp.matchmaking import search_range_for_wait


def battle_hub_embed(state: dict[str, Any], *, manager_name: str) -> discord.Embed:
    pvp_on = bool(state.get("battle_pvp_enabled"))
    energy = state.get("action_energy", "?")
    lp = state.get("global_lp", 0)
    div = state.get("global_division", "Unknown")
    pvp_cost = state.get("pvp_energy_cost", 20)
    prac_cost = state.get("practice_energy_cost", 10)
    daily = state.get("daily_pvp_count", 0)
    daily_cap = state.get("daily_pvp_cap", 5)
    backfill_count = state.get("daily_backfill_count", 0)
    backfill_cap = state.get("daily_backfill_cap", 3)

    if pvp_on:
        desc = (
            f"Manager: **{manager_name}**\n"
            f"Global Division: **{div}**\n"
            f"Global LP: **{lp:,}**\n"
            f"Action Energy: **{energy}**\n\n"
            f"**⚔️ Ranked Battle**\n"
            f"Find a live manager first. If none is available,\n"
            f"you'll face a recent real-club snapshot within seconds.\n"
            f"Ranked matches today: **{daily}/{daily_cap}** (Backfills used: **{backfill_count}/{backfill_cap}**).\n\n"
            f"**🤖 AI Practice**\n"
            f"Costs **{prac_cost}** ⚡ and awards **0 LP**."
        )
    else:
        desc = (
            f"Welcome to the Battle Arena, Manager **{manager_name}**!\n"
            f"Bot battles consume energy. Friendly matches are free — no energy, coins, or XP.\n"
            f"(Ranked PvP is not enabled in this guild yet.)"
        )

    embed = discord.Embed(
        title="🏟️ ElevenBoss Battle Arena",
        description=desc,
        color=0x00FF87,
    )
    q = state.get("queue")
    if q:
        embed.add_field(
            name="Queue",
            value=f"Status: **{q.get('status')}** · expires <t:{int(datetime.fromisoformat(str(q['expires_at']).replace('Z', '+00:00')).timestamp())}:R>",
            inline=False,
        )
    return embed


def searching_embed(
    *,
    division: str,
    global_lp: int,
    xi_rating: float,
    joined_at: datetime,
    now: datetime | None = None,
) -> discord.Embed:
    now = now or datetime.now(timezone.utc)
    if joined_at.tzinfo is None:
        joined_at = joined_at.replace(tzinfo=timezone.utc)
    wait = max(0.0, (now - joined_at).total_seconds())
    band = search_range_for_wait(wait)

    if wait < 5:
        stage_title = "🔎 Finding Your Opponent"
        stage_desc = (
            f"Searching for:\n"
            f"1. 🟢 Live manager\n"
            f"2. 👻 Ghost manager snapshot\n"
            f"3. 🤖 Ranked AI backfill\n\n"
            f"Estimated start: under **10 seconds**\n"
            f"Current phase: **Live manager search**"
        )
    else:
        stage_title = "🔎 Expanding Search Range"
        stage_desc = (
            f"No close live manager found yet.\n"
            f"Checking wider divisions before selecting a ghost opponent.\n\n"
            f"Estimated start: under **5 seconds**\n"
            f"Current phase: **Expanded search**"
        )

    embed = discord.Embed(
        title=stage_title,
        description=(
            f"Division: **{division}** · **{global_lp:,} LP** · **{xi_rating:.1f} OVR**\n\n"
            f"{stage_desc}\n\n"
            f"• Division Δ ≤ **{band.max_division_delta}**\n"
            f"• ±**{band.max_lp_delta}** LP\n"
            f"• ±**{band.max_ovr_delta:g}** OVR\n\n"
            f"Searching: **{int(wait)}s** | No energy spent yet."
        ),
        color=0x3498DB,
    )
    return embed


def opponent_found_embed(
    *,
    home_name: str,
    home_div: str,
    home_lp: int,
    home_ovr: float,
    away_name: str,
    away_div: str,
    away_lp: int,
    away_ovr: float,
    opponent_mode: str = "live",
    snapshot_age_seconds: int | None = None,
) -> discord.Embed:
    if opponent_mode == "ghost":
        badge = "👻 GHOST MANAGER MATCH"
        age_str = f"{snapshot_age_seconds // 3600}h ago" if snapshot_age_seconds and snapshot_age_seconds >= 3600 else "recent"
        footer_text = f"Facing a frozen squad snapshot ({age_str}). Reduced Ranked rewards apply."
        color = 0x9B59B6
    elif opponent_mode == "ai_backfill":
        badge = "🤖 RANKED AI BACKFILL MATCH"
        footer_text = "Calibrated Ranked AI opponent. Reduced Ranked rewards apply."
        color = 0x34495E
    else:
        badge = "🟢 LIVE MANAGER MATCH"
        footer_text = "Both managers are live in this stadium! Full Ranked rewards apply."
        color = 0x2ECC71

    embed = discord.Embed(
        title=badge,
        description=(
            f"**{home_name}**\n{home_div} · {home_lp:,} LP · {home_ovr:.1f} OVR\n\n"
            f"⚔️ **VS** ⚔️\n\n"
            f"**{away_name}**\n{away_div} · {away_lp:,} LP · {away_ovr:.1f} OVR"
        ),
        color=color,
    )
    embed.set_footer(text=footer_text)
    return embed


def queue_timeout_embed() -> discord.Embed:
    return discord.Embed(
        title="⌛ No Opponent Found",
        description=(
            "Search timed out.\n\n"
            "Choose **Continue Search**, **AI Practice**, or **Cancel**."
        ),
        color=0x95A5A6,
    )


def practice_result_footer() -> str:
    return "AI Practice — No Global LP · No rivalry progress"


def match_history_mode_label(match_type: str | None, opponent_mode: str | None = None) -> str:
    if match_type == "pvp":
        if opponent_mode == "ghost":
            return "👻 Ghost PvP"
        elif opponent_mode == "ai_backfill":
            return "🤖 Ranked AI"
        return "🟢 Ranked PvP"
    return {
        "practice": "AI Practice",
        "friendly": "Friendly",
        "league": "League",
        "bot": "Bot Battle",
    }.get(match_type or "bot", match_type or "Match")


def format_rivalry_events(events: list[Any]) -> str:
    lines: list[str] = []
    for ev in events[:6]:
        if isinstance(ev, dict):
            msg = ev.get("message") or ev.get("code") or str(ev)
        else:
            msg = str(ev)
        lines.append(f"• {msg}")
    return "\n".join(lines) if lines else "—"


async def rivalry_prematch_field(
    db: Any,
    home_id: int,
    away_id: int,
    home_p: dict,
    away_p: dict,
) -> str:
    try:
        from apps.discord_bot.core.pvp_rpc import call_get_rivalry_detail
        detail = await call_get_rivalry_detail(db, home_id, away_id)
        if not detail or not detail.get("meetings"):
            return f"First official meeting between {home_p['club_name']} and {away_p['club_name']}!"
        m = detail.get("meetings", 0)
        a_w = detail.get("a_wins", 0)
        b_w = detail.get("b_wins", 0)
        d = detail.get("draws", 0)
        status = detail.get("status", "tracking").upper()
        return f"**{status} RIVALRY** · Meetings: **{m}** (W{a_w}-D{d}-L{b_w})"
    except Exception:
        return ""

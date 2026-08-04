# apps/discord_bot/embeds/pvp_embeds.py
"""Ranked PvP / Practice embeds (Feature 053)."""
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

    if pvp_on:
        desc = (
            f"Manager: **{manager_name}**\n"
            f"Global Division: **{div}**\n"
            f"Global LP: **{lp:,}**\n"
            f"Action Energy: **{energy}**\n\n"
            f"**Ranked PvP** — play human managers to earn Global LP "
            f"(energy **{pvp_cost}** when the match finalizes).\n"
            f"Today: **{daily}/{daily_cap}** ranked.\n"
            f"**AI Practice** costs **{prac_cost}** ⚡ and awards **no Global LP**.\n"
            f"Friendly remains a free sandbox."
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
    embed = discord.Embed(
        title="🔎 Searching for an Opponent",
        description=(
            f"Division: **{division}**\n"
            f"Global LP: **{global_lp:,}**\n"
            f"Starting XI: **{xi_rating:.1f} OVR**\n\n"
            f"Search range:\n"
            f"• Division Δ ≤ **{band.max_division_delta}**\n"
            f"• ±**{band.max_lp_delta}** LP\n"
            f"• ±**{band.max_ovr_delta:g}** XI OVR\n\n"
            f"Searching: **{int(wait)}** seconds\n\n"
            f"No energy has been spent."
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
) -> discord.Embed:
    return discord.Embed(
        title="⚔️ Opponent Found",
        description=(
            f"**{home_name}**\n{home_div} · {home_lp:,} LP · {home_ovr:.1f} OVR\n\n"
            f"**vs**\n\n"
            f"**{away_name}**\n{away_div} · {away_lp:,} LP · {away_ovr:.1f} OVR\n\n"
            f"Opening the stadium…"
        ),
        color=0xE67E22,
    )


def queue_timeout_embed() -> discord.Embed:
    return discord.Embed(
        title="⌛ No Opponent Found",
        description=(
            "Search timed out.\n\n"
            "Choose **Continue Search**, **AI Practice**, or **Cancel**.\n"
            "The system will **never** silently replace Ranked PvP with AI."
        ),
        color=0x95A5A6,
    )


def practice_result_footer() -> str:
    return "AI Practice — No Global LP · No rivalry progress"


def match_history_mode_label(match_type: str | None) -> str:
    return {
        "pvp": "Ranked PvP",
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
    home_p: dict[str, Any],
    away_p: dict[str, Any],
) -> str | None:
    """Presentation-only pre-match rivalry blurb when active and callouts enabled."""
    try:
        if home_p.get("pvp_rivalry_callouts") is False and away_p.get("pvp_rivalry_callouts") is False:
            return None
        res = await db.rpc(
            "get_rivalry_detail",
            {"p_viewer_id": home_id, "p_opponent_id": away_id},
        ).execute()
        data = res.data if isinstance(res.data, dict) else {}
        if not data.get("found") or data.get("status") != "active":
            return None
        meetings = int(data.get("meetings") or 0)
        a_wins = int(data.get("a_wins") or 0)
        b_wins = int(data.get("b_wins") or 0)
        a_id = int(data.get("manager_a_id") or 0)
        if home_id == a_id:
            my_w, their_w = a_wins, b_wins
        else:
            my_w, their_w = b_wins, a_wins
        lead = (
            f"{home_p.get('club_name')} leads {my_w}–{their_w}"
            if my_w > their_w
            else (
                f"{away_p.get('club_name')} leads {their_w}–{my_w}"
                if their_w > my_w
                else f"Series tied {my_w}–{their_w}"
            )
        )
        return f"Meeting **#{meetings}** · {lead}"
    except Exception:
        return None


def rivalries_list_embed(payload: dict[str, Any], *, manager_name: str) -> discord.Embed:
    rows = payload.get("rivalries") or []
    embed = discord.Embed(
        title="🔥 Manager Rivalries",
        description=f"Rivalries for **{manager_name}** (presentation only — no sim buffs).",
        color=0xE74C3C,
    )
    if not rows:
        embed.add_field(
            name="None yet",
            value="Play **3 Ranked PvP** meetings with the same manager within 30 days to activate a rivalry.",
            inline=False,
        )
        return embed
    for row in rows[:10]:
        status = row.get("status", "?")
        opp = row.get("opponent_id")
        embed.add_field(
            name=f"<@{opp}> · {status}",
            value=(
                f"H2H **{row.get('my_wins', 0)}–{row.get('their_wins', 0)}** "
                f"({row.get('draws', 0)} draws) · {row.get('meetings', 0)} meetings"
            ),
            inline=False,
        )
    return embed


def rivalry_detail_embed(detail: dict[str, Any], *, opponent_id: int, viewer_id: int) -> discord.Embed:
    a_id = int(detail.get("manager_a_id") or 0)
    if viewer_id == a_id:
        my_w, their_w = int(detail.get("a_wins") or 0), int(detail.get("b_wins") or 0)
        my_g, their_g = int(detail.get("a_goals") or 0), int(detail.get("b_goals") or 0)
    else:
        my_w, their_w = int(detail.get("b_wins") or 0), int(detail.get("a_wins") or 0)
        my_g, their_g = int(detail.get("b_goals") or 0), int(detail.get("a_goals") or 0)
    embed = discord.Embed(
        title=f"🔥 Rivalry vs <@{opponent_id}>",
        description=f"Status: **{detail.get('status')}** · Meetings: **{detail.get('meetings', 0)}**",
        color=0xC0392B,
    )
    embed.add_field(name="Head-to-head", value=f"**{my_w}–{their_w}** ({detail.get('draws', 0)} draws)", inline=True)
    embed.add_field(name="Goals", value=f"**{my_g}–{their_g}**", inline=True)
    streak_owner = detail.get("current_streak_owner")
    streak_n = detail.get("current_streak_count") or 0
    if streak_owner and streak_n:
        embed.add_field(name="Streak", value=f"<@{streak_owner}> ×{streak_n}", inline=True)
    recent = detail.get("recent") or []
    if recent:
        lines = []
        for m in recent[:5]:
            lines.append(
                f"`{m.get('result', '?')}` {m.get('goals_for', 0)}–{m.get('goals_against', 0)} "
                f"(LP {int(m.get('lp_delta') or 0):+d})"
            )
        embed.add_field(name="Last 5 Ranked", value="\n".join(lines), inline=False)
    badges = detail.get("viewer_badges") or []
    if badges:
        embed.add_field(name="Badges", value=", ".join(f"`{b}`" for b in badges[:8]), inline=False)
    prefs = detail.get("prefs") or {}
    embed.set_footer(
        text=(
            f"DMs={'on' if prefs.get('dms', True) else 'off'} · "
            f"Callouts={'on' if prefs.get('callouts', True) else 'off'} · "
            f"LB={'on' if prefs.get('lb_visible', True) else 'off'} · "
            f"Blocked={'yes' if detail.get('blocked') else 'no'}"
        )
    )
    return embed


def hottest_rivalries_embed(payload: dict[str, Any]) -> discord.Embed:
    rows = payload.get("rivalries") or []
    embed = discord.Embed(
        title="🌡️ Hottest Rivalries",
        description="Server board (visibility prefs respected).",
        color=0xE67E22,
    )
    if not rows:
        embed.description = "No active rivalries to show yet."
        return embed
    for i, row in enumerate(rows[:10], start=1):
        embed.add_field(
            name=f"#{i}",
            value=(
                f"<@{row.get('manager_a_id')}> vs <@{row.get('manager_b_id')}>\n"
                f"{row.get('a_wins', 0)}–{row.get('b_wins', 0)} · "
                f"{row.get('meetings_30d', row.get('meetings', 0))} meetings (30d)"
            ),
            inline=False,
        )
    return embed

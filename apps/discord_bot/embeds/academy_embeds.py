# apps/discord_bot/embeds/academy_embeds.py
"""Youth Academy Manage Academy embeds (015)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord

from player_engine import READY_OVR_DEFAULT, academy_daily_points, is_promotion_ready, star_band

_POS_EMOJI = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
_COLOR = 0x2ECC71


def _progress_bar(progress: int, width: int = 8) -> str:
    filled = max(0, min(width, int(progress) * width // 100))
    return "▓" * filled + "░" * (width - filled)


def days_until_next_monday_utc(now: datetime | None = None) -> int:
    """0 if today is Monday UTC, else 1–6."""
    n = now or datetime.now(timezone.utc)
    # Monday = 0
    return (7 - n.weekday()) % 7


def next_intake_line(now: datetime | None = None) -> str:
    days = days_until_next_monday_utc(now)
    if days == 0:
        return "Next free intake: **today** (Monday UTC)"
    if days == 1:
        return "Next free intake: **tomorrow** (Monday UTC)"
    return f"Next free intake: in **{days} days** (Monday UTC)"


def scout_status_line(player: dict, report: dict | None) -> str:
    if report and report.get("signed_card_id") is None:
        exp = report.get("expires_at", "?")
        return f"Scout report **ready** — expires `{exp}` (sign one prospect below)"
    finishes = player.get("scouting_finishes_at")
    if finishes:
        try:
            ts = datetime.fromisoformat(str(finishes).replace("Z", "+00:00"))
            if ts > datetime.now(timezone.utc):
                return f"Scout in progress — finishes `<t:{int(ts.timestamp())}:R>`"
        except ValueError:
            return f"Scout in progress — finishes `{finishes}`"
    return "Scout: **idle** (optional paid search)"


def prospect_line(card: dict, *, ready_ovr: int = READY_OVR_DEFAULT) -> str:
    pos = card.get("position", "?")
    name = card.get("name", "?")
    age = card.get("age", "?")
    ovr = int(card.get("overall", 0))
    pot = int(card.get("potential", ovr))
    prog = int(card.get("academy_progress", 0))
    stars = "⭐" * star_band(pot)
    ready = " · **Ready**" if is_promotion_ready(ovr, ready_ovr) else ""
    bar = _progress_bar(prog)
    return (
        f"{_POS_EMOJI.get(pos, '🏃')} **{pos}** — {name} "
        f"({age} yrs · **{ovr}** OVR · {stars} · `{bar}` {prog}/100){ready}"
    )


def academy_hub_embed(
    player: dict,
    prospects: list[dict],
    *,
    slots_used: int,
    slots_cap: int,
    report: dict | None = None,
    ready_ovr: int = READY_OVR_DEFAULT,
) -> discord.Embed:
    level = int(player.get("youth_academy_level", 1))
    club = player.get("club_name") or "Your Club"
    coins = int(player.get("coins", 0))
    daily = academy_daily_points(level, 80)

    desc = (
        f"**{club}** · YA **L{level}** · Slots **{slots_used}/{slots_cap}** · 🪙 `{coins:,}`\n"
        f"Weekly intake → grow in academy → promote/release. Paid scout is optional.\n"
        f"{next_intake_line()}\n"
        f"{scout_status_line(player, report)}\n"
        f"_Passive growth ~**{daily}** pts/day toward next OVR (higher YA = faster)._"
    )
    embed = discord.Embed(title="🌱 Manage Academy", description=desc, color=_COLOR)
    if not prospects:
        embed.add_field(
            name="Academy prospects",
            value="_Empty — free Monday intake seats here when slots are free._",
            inline=False,
        )
    else:
        lines = [prospect_line(c, ready_ovr=ready_ovr) for c in prospects[:slots_cap]]
        embed.add_field(name=f"Academy prospects ({len(prospects)})", value="\n".join(lines), inline=False)
    embed.set_footer(text="Ready ≈ 65 OVR guideline · Early promote allowed · /profile → Manage Academy")
    return embed


def scout_shortlist_embed(tier: str, prospects: list[dict], *, report_id: str) -> discord.Embed:
    """Fog by tier: quick=pos+stars; standard=+OVR; deep=+OVR+POT."""
    lines: list[str] = []
    for i, p in enumerate(prospects[:3]):
        pos = p.get("position", "?")
        name = p.get("name", f"Prospect {i + 1}")
        pot = int(p.get("potential", p.get("overall", 50)))
        stars = "⭐" * star_band(pot)
        ovr = int(p.get("overall", 0))
        if tier == "quick":
            detail = f"{stars}"
        elif tier == "standard":
            detail = f"**{ovr}** OVR · {stars}"
        else:
            detail = f"**{ovr}** OVR · 📊 {pot} POT · {stars}"
        lines.append(f"`{i}` {_POS_EMOJI.get(pos, '🏃')} **{pos}** — {name} ({detail})")
    return discord.Embed(
        title=f"🔍 Scout Report ({tier})",
        description=(
            "Sign **one** prospect into a free academy slot.\n\n" + "\n".join(lines)
        ),
        color=_COLOR,
    ).set_footer(text=f"Report `{report_id[:8]}…` · fog: Quick high → Deep low")

# apps/discord_bot/embeds/academy_embeds.py
"""Youth Academy Manage Academy embeds (015 / 051 V2)."""
from __future__ import annotations

from datetime import datetime, timezone

import discord

from player_engine import (
    READY_OVR_DEFAULT,
    academy_daily_points,
    is_promotion_ready,
    star_band_from_interval,
)

_POS_EMOJI = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
_COLOR = 0x2ECC71


def _progress_bar(progress: int, width: int = 8) -> str:
    filled = max(0, min(width, int(progress) * width // 100))
    return "▓" * filled + "░" * (width - filled)


def days_until_next_monday_utc(now: datetime | None = None) -> int:
    """0 if today is Monday UTC, else 1–6."""
    n = now or datetime.now(timezone.utc)
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
        return f"Discovery report **ready** — expires `{exp}` (sign one prospect below)"
    finishes = player.get("scouting_finishes_at")
    if finishes:
        try:
            ts = datetime.fromisoformat(str(finishes).replace("Z", "+00:00"))
            if ts > datetime.now(timezone.utc):
                return f"Discovery scout in progress — finishes `<t:{int(ts.timestamp())}:R>`"
        except ValueError:
            return f"Discovery scout in progress — finishes `{finishes}`"
    return "Discovery scout: **idle** (optional paid search)"


def _visible_range(card: dict) -> tuple[int, int]:
    pot = int(card.get("potential", card.get("overall", 0)))
    lo = card.get("pot_visible_lo")
    hi = card.get("pot_visible_hi")
    if lo is None or hi is None:
        return pot, pot
    return int(lo), int(hi)


def prospect_line(card: dict, *, ready_ovr: int = READY_OVR_DEFAULT) -> str:
    pos = card.get("position", "?")
    name = card.get("name", "?")
    age = card.get("age", "?")
    ovr = int(card.get("overall", 0))
    rarity = card.get("rarity", "?")
    prog = int(card.get("academy_progress", 0))
    lo, hi = _visible_range(card)
    stars = "⭐" * star_band_from_interval(lo, hi)
    ready = " · **Ready**" if is_promotion_ready(ovr, ready_ovr) else ""
    aging = ""
    if card.get("academy_age_out_pending_at"):
        aging = " · ⚠️ **Age-out pending**"
    elif card.get("academy_warned_aging_at"):
        aging = " · ⚠️ Aging"
    bar = _progress_bar(prog)
    return (
        f"{_POS_EMOJI.get(pos, '🏃')} **{pos}** — {name} "
        f"({age} yrs · {rarity} · **{ovr}** OVR · POT `{lo}–{hi}` · {stars} · `{bar}` {prog}/100)"
        f"{ready}{aging}"
    )


def academy_hub_embed(
    player: dict,
    prospects: list[dict],
    *,
    slots_used: int,
    slots_cap: int,
    report: dict | None = None,
    ready_ovr: int = READY_OVR_DEFAULT,
    promotes_used: int = 0,
    promote_cap: int = 2,
    origin: str = "development",
) -> discord.Embed:
    level = int(player.get("youth_academy_level", 1))
    club = player.get("club_name") or "Your Club"
    coins = int(player.get("coins", 0))
    daily = academy_daily_points(level, 80)
    over = " · **over capacity**" if slots_used > slots_cap else ""

    origin_hint = {
        "development": "/development → Youth Academy",
        "squad": "/squad → Youth",
        "profile": "/profile → Manage Academy",
    }.get(origin, "/development → Youth Academy")

    desc = (
        f"**{club}** · YA **L{level}** · Slots **{slots_used}/{slots_cap}**{over} · 🪙 `{coins:,}`\n"
        f"Weekly promotes **{promotes_used}/{promote_cap}** · intake → grow → promote/release.\n"
        f"{next_intake_line()}\n"
        f"{scout_status_line(player, report)}\n"
        f"_Passive growth ~**{daily}** pts/day toward next OVR (higher YA = faster)._"
    )
    embed = discord.Embed(title="🌱 Youth Academy", description=desc, color=_COLOR)
    if not prospects:
        embed.add_field(
            name="Academy prospects",
            value="_Empty — free Monday intake seats here when slots are free._",
            inline=False,
        )
    else:
        lines = [prospect_line(c, ready_ovr=ready_ovr) for c in prospects[: max(slots_cap, slots_used, 10)]]
        embed.add_field(name=f"Academy prospects ({len(prospects)})", value="\n".join(lines), inline=False)
    embed.set_footer(text=f"Ready is advisory · Early promote allowed · {origin_hint}")
    return embed


def graduation_embed(result: dict) -> discord.Embed:
    name = result.get("name", "Graduate")
    ovr = result.get("overall", "?")
    rarity = result.get("rarity", "?")
    age = result.get("age", "?")
    days = result.get("days_developed", "?")
    early = result.get("early_promote")
    fee = result.get("fee", 0)
    return discord.Embed(
        title="🎓 Graduation",
        description=(
            f"**{name}** joins the senior club.\n"
            f"**{ovr}** OVR · {rarity} · age {age} · developed **{days}** days"
            + (" · early promote" if early else "")
            + (f"\nFee: 🪙 `{fee:,}`" if fee else "")
        ),
        color=_COLOR,
    )


def scout_shortlist_embed(tier: str, prospects: list[dict], *, report_id: str) -> discord.Embed:
    """Fog by tier: quick=pos+stars; standard=+OVR; deep=tight range (not exact POT)."""
    lines: list[str] = []
    for i, p in enumerate(prospects[:3]):
        pos = p.get("position", "?")
        name = p.get("name", f"Prospect {i + 1}")
        pot = int(p.get("potential", p.get("overall", 50)))
        rarity = p.get("rarity", "Common")
        lo = p.get("pot_visible_lo")
        hi = p.get("pot_visible_hi")
        if lo is None or hi is None:
            # Fog discovery payloads that lack stored bounds
            span = {"quick": 10, "standard": 6, "deep": 3}.get(tier, 8)
            half = span // 2
            lo = max(1, pot - half)
            hi = pot + (span - 1 - half)
        lo, hi = int(lo), int(hi)
        stars = "⭐" * star_band_from_interval(lo, hi)
        ovr = int(p.get("overall", 0))
        if tier == "quick":
            detail = f"{rarity} · {stars}"
        elif tier == "standard":
            detail = f"{rarity} · **{ovr}** OVR · {stars}"
        else:
            detail = f"{rarity} · **{ovr}** OVR · POT `{lo}–{hi}` · {stars}"
        lines.append(f"`{i}` {_POS_EMOJI.get(pos, '🏃')} **{pos}** — {name} ({detail})")
    return discord.Embed(
        title=f"🔍 Discovery Report ({tier})",
        description=(
            "Sign **one** prospect into a free academy slot.\n\n" + "\n".join(lines)
        ),
        color=_COLOR,
    ).set_footer(text=f"Report `{report_id[:8]}…` · Deep shows a tight range, not exact POT")


def compact_academy_status(slots_used: int, slots_cap: int, now: datetime | None = None) -> str:
    return f"🌱 Academy **{slots_used}/{slots_cap}** · {next_intake_line(now)}"

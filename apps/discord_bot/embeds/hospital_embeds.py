# apps/discord_bot/embeds/hospital_embeds.py
"""Hospital / Medical Center embeds for Club Facilities."""
from __future__ import annotations

from datetime import datetime, timezone

import discord

from economy import (
    HOSPITAL_MAX_LEVEL,
    hospital_bed_capacity,
    hospital_recovery_multiplier,
    hospital_upgrade_cost,
)
from player_engine import (
    MODERATE_BASE_DAYS,
    TIER_NAMES,
    facility_bonus_pct,
    intensity_label,
    intensity_tier_for_division,
    intensity_vibe,
    recovery_days_for_intensity,
    untreated_base_days,
)


def format_recovery_eta(expected: str | None) -> str:
    """Shared ETA label for hospital panel + profile summary."""
    if not expected:
        return "unknown"
    try:
        ts = datetime.fromisoformat(str(expected).replace("Z", "+00:00"))
        days = max(0, (ts - datetime.now(timezone.utc)).days)
        return f"<t:{int(ts.timestamp())}:D> (~{days}d)"
    except ValueError:
        return str(expected)


def _eta_str(expected: str | None) -> str:
    return format_recovery_eta(expected)


def _resolve_intensity(player: dict) -> int:
    if player.get("intensity_tier") is not None:
        return max(1, min(3, int(player["intensity_tier"])))
    return intensity_tier_for_division(player.get("division"))


def injury_breakdown_line(
    *,
    severity: int,
    intensity_tier: int,
    hospital_level: int,
    in_hospital: bool,
    division: str | None = None,
) -> str:
    """Profile / hospital patient math copy."""
    base = int(round(untreated_base_days(severity, intensity_tier)))
    label = intensity_label(intensity_tier)
    div = division or label
    if in_hospital:
        bonus = facility_bonus_pct(hospital_level)
        return f"(Base: {base}d @ {div} | Facility Bonus: −{bonus}%)"
    return f"(Base: {base}d @ {div} | Facility Bonus: 0% untreated)"


def hospital_panel_embed(
    player: dict,
    *,
    patients: list[dict],
    waiting: list[dict],
) -> discord.Embed:
    level = int(player.get("hospital_level", 0))
    beds = hospital_bed_capacity(level)
    occupied = len(patients)
    mult = hospital_recovery_multiplier(level)
    faster = int(round((1.0 - mult) * 100))
    intensity = _resolve_intensity(player)
    division = str(player.get("division") or "Grassroots")
    vibe = intensity_vibe(intensity)
    label = intensity_label(intensity)

    intensity_lines = [
        f"⚠️ League Intensity: **{label}** ({division}) — {vibe}",
    ]
    if intensity >= 3:
        intensity_lines.append(
            "Base recovery times are longer than lower leagues."
        )
    elif intensity == 1:
        intensity_lines.append("Forgiving medical clocks for lower divisions.")

    embed = discord.Embed(
        title=f"🏥 Hospital — Level {level}/{HOSPITAL_MAX_LEVEL}",
        description=(
            "\n".join(intensity_lines)
            + f"\n🛏️ Beds: **{occupied}/{beds}** · "
            f"Recovery: **{mult:.2f}×** ({faster}% faster than untreated)\n"
            f"🪙 Balance: `{int(player.get('coins', 0)):,}`"
        ),
        color=0xE74C3C,
    )

    if patients:
        lines = []
        for p in patients:
            card = p.get("player_cards") or p
            name = card.get("name", "Player")
            tier = int(p.get("injury_tier") or card.get("injury_tier") or 1)
            breakdown = injury_breakdown_line(
                severity=tier,
                intensity_tier=intensity,
                hospital_level=level,
                in_hospital=True,
                division=division,
            )
            lines.append(
                f"🔴 **{name}** — {TIER_NAMES.get(tier, 'Injured')} · "
                f"Returns {_eta_str(p.get('expected_recovery_date'))}\n{breakdown}"
            )
        embed.add_field(name="Current Patients", value="\n".join(lines)[:1000], inline=False)
    else:
        embed.add_field(name="Current Patients", value="*No one admitted.*", inline=False)

    if waiting:
        lines = []
        for card in waiting:
            tier = int(card.get("injury_tier") or 1)
            breakdown = injury_breakdown_line(
                severity=tier,
                intensity_tier=intensity,
                hospital_level=0,
                in_hospital=False,
                division=division,
            )
            lines.append(
                f"⏳ **{card.get('name', 'Player')}** — {TIER_NAMES.get(tier, 'Injured')} · "
                f"{int(card.get('injury_recovery_days') or 0)}d untreated\n{breakdown}"
            )
        embed.add_field(name="Waiting (no bed)", value="\n".join(lines)[:1000], inline=False)
    else:
        embed.add_field(name="Waiting (no bed)", value="*Nobody waiting.*", inline=False)

    cost = hospital_upgrade_cost(level)
    if cost is not None:
        embed.set_footer(text=f"Next upgrade: {cost:,} coins · Moderate base @ intensity: {MODERATE_BASE_DAYS.get(intensity, 3)}d")
    else:
        embed.set_footer(text="Hospital max level")

    return embed


def format_card_injury_report(
    card: dict,
    *,
    intensity_tier: int,
    hospital_level: int,
    division: str | None = None,
    expected_recovery_date: str | None = None,
) -> str | None:
    """Full injury report for a single card (profile / squad). None if healthy."""
    severity = card.get("injury_tier")
    if not severity:
        return None
    sev = int(severity)
    in_hosp = bool(card.get("in_hospital"))
    eta = format_recovery_eta(expected_recovery_date) if expected_recovery_date else (
        f"{int(card.get('injury_recovery_days') or 0)}d untreated"
    )
    days = recovery_days_for_intensity(
        sev, intensity_tier, hospital_level if in_hosp else 0
    )
    breakdown = injury_breakdown_line(
        severity=sev,
        intensity_tier=intensity_tier,
        hospital_level=hospital_level if in_hosp else 0,
        in_hospital=in_hosp,
        division=division,
    )
    return (
        f"🔴 **INJURED: {TIER_NAMES.get(sev, 'Injured')}**\n"
        f"📅 Expected Return: {eta} (~{days}d formula)\n"
        f"{breakdown}"
    )

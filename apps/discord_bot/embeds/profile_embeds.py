# apps/discord_bot/embeds/profile_embeds.py
"""Club profile dashboard field builders (finance + hospital summary)."""
from __future__ import annotations

from economy import hospital_bed_capacity, hospital_recovery_multiplier

from apps.discord_bot.embeds.hospital_embeds import format_recovery_eta

HOSPITAL_UNAVAILABLE = "Hospital status unavailable — try again or open Manage Hospital."
L0_EMPTY = "No Hospital yet — open Manage Hospital on your club Profile to build one."
MAX_PATIENT_LINES = 5


def format_finance_section(coins: int, gems: int) -> str:
    return f"🪙 **Coins**: `{int(coins):,}`\n💎 **Gems**: `{int(gems):,}`"


def format_hospital_summary(
    hospital_level: int,
    patients: list[dict] | None,
    *,
    unavailable: bool = False,
) -> str:
    """Profile Hospital section copy. L0 never invents bed fractions (FR-004)."""
    if unavailable:
        return HOSPITAL_UNAVAILABLE

    level = int(hospital_level or 0)
    if level <= 0:
        return L0_EMPTY

    rows = list(patients or [])
    occupied = len(rows)
    beds = hospital_bed_capacity(level)
    mult = hospital_recovery_multiplier(level)
    faster = int(round((1.0 - mult) * 100))
    header = (
        f"**Level {level}** · 🛏️ **{occupied}/{beds}** beds · "
        f"Recovery **{mult:.2f}×** ({faster}% faster than untreated)"
    )

    if not rows:
        return f"{header}\n*No injuries*"

    lines: list[str] = []
    for p in rows[:MAX_PATIENT_LINES]:
        card = p.get("player_cards") or p
        name = card.get("name", "Player")
        eta = format_recovery_eta(p.get("expected_recovery_date"))
        lines.append(f"• **{name}** — back {eta}")

    overflow = occupied - MAX_PATIENT_LINES
    if overflow > 0:
        lines.append(f"*…and **{overflow}** more — open Manage Hospital*")

    return header + "\n" + "\n".join(lines)

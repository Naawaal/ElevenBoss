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
from player_engine import TIER_NAMES


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

    embed = discord.Embed(
        title=f"🏥 Hospital — Level {level}/{HOSPITAL_MAX_LEVEL}",
        description=(
            f"🛏️ Beds: **{occupied}/{beds}** · "
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
            lines.append(
                f"🔴 **{name}** — {TIER_NAMES.get(tier, 'Injured')} · "
                f"Returns {_eta_str(p.get('expected_recovery_date'))}"
            )
        embed.add_field(name="Current Patients", value="\n".join(lines)[:1000], inline=False)
    else:
        embed.add_field(name="Current Patients", value="*No one admitted.*", inline=False)

    if waiting:
        lines = []
        for card in waiting:
            tier = int(card.get("injury_tier") or 1)
            lines.append(
                f"⏳ **{card.get('name', 'Player')}** — {TIER_NAMES.get(tier, 'Injured')} · "
                f"{int(card.get('injury_recovery_days') or 0)}d untreated"
            )
        embed.add_field(name="Waiting (no bed)", value="\n".join(lines)[:1000], inline=False)
    else:
        embed.add_field(name="Waiting (no bed)", value="*Nobody waiting.*", inline=False)

    cost = hospital_upgrade_cost(level)
    if cost is None:
        embed.add_field(name="Upgrade", value="✅ Max level", inline=False)
    else:
        embed.add_field(
            name=f"Upgrade to Level {level + 1}",
            value=(
                f"💰 **{cost:,}** coins · 🛏️ {hospital_bed_capacity(level + 1)} beds · "
                f"⚡ {hospital_recovery_multiplier(level + 1):.2f}× recovery\n"
                "Shares the **1 facility upgrade / UTC week** cooldown with YA & Training Ground."
            ),
            inline=False,
        )
    embed.set_footer(text="Injuries: only tired players (fatigue < 75), max 1 per match.")
    return embed

# apps/discord_bot/embeds/youth_intake_embeds.py
from __future__ import annotations

import discord
from gacha import GachaPlayer

from apps.discord_bot.embeds.onboarding_embeds import COLOR_EMERALD, COLOR_GRAY


def youth_intake_embed(players: list[GachaPlayer], *, club_name: str | None = None) -> discord.Embed:
    """Seasonal youth academy intake notification embed."""
    header = (
        f"**{club_name}** received new academy prospects this week!\n\n"
        if club_name
        else "Your youth academy has produced new prospects this week!\n\n"
    )
    ordered = sorted(players, key=lambda p: ["GK", "DEF", "MID", "FWD"].index(p.position))
    emoji_map = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
    lines = [
        f"{emoji_map.get(p.position, '🏃')} **{p.position}** — {p.name} "
        f"({p.overall} OVR · {p.role} · {p.age} yrs · 📊 {p.potential} POT)"
        for p in ordered
    ]
    return discord.Embed(
        title="🌱 Youth Academy Intake",
        description=header + "\n".join(lines),
        color=COLOR_GRAY,
    ).set_footer(text="Prospects join your roster — assign them in /squad when ready.")

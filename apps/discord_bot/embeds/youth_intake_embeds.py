# apps/discord_bot/embeds/youth_intake_embeds.py
from __future__ import annotations

import discord
from gacha import GachaPlayer

from apps.discord_bot.embeds.onboarding_embeds import COLOR_GRAY
from player_engine import init_visible_range, star_band_from_interval


def youth_intake_embed(
    players: list[GachaPlayer],
    *,
    club_name: str | None = None,
    seated: int | None = None,
    skipped: int | None = None,
    slots_used: int | None = None,
    slots_cap: int | None = None,
    academy_level: int = 1,
    capacity_blocked: bool = False,
) -> discord.Embed:
    """Seasonal youth academy intake notification embed."""
    header = (
        f"**{club_name}** received new academy prospects this week!\n\n"
        if club_name
        else "Your youth academy has produced new prospects this week!\n\n"
    )
    if capacity_blocked and not seated:
        header = (
            f"**{club_name}** " if club_name else ""
        ) + (
            "Monday intake found **no free academy seats** — "
            "promote or release prospects to free capacity.\n\n"
        )
    elif seated is not None:
        header += f"**Seated in academy:** {seated}"
        if slots_used is not None and slots_cap is not None:
            header += f" · Slots **{slots_used}/{slots_cap}**"
        header += "\n"
        if skipped:
            header += (
                f"**Skipped (academy full):** {skipped} — "
                "release or promote in Youth Academy to free slots.\n"
            )
        header += "\n"
    ordered = sorted(players, key=lambda p: ["GK", "DEF", "MID", "FWD"].index(p.position))
    emoji_map = {"GK": "🧤", "DEF": "🛡️", "MID": "👟", "FWD": "⚽"}
    lines: list[str] = []
    for p in ordered:
        lo, hi = init_visible_range(int(p.potential), str(p.rarity), academy_level)
        stars = "⭐" * star_band_from_interval(lo, hi)
        lines.append(
            f"{emoji_map.get(p.position, '🏃')} **{p.position}** — {p.name} "
            f"({p.overall} OVR · {p.rarity} · {p.age} yrs · POT `{lo}–{hi}` · {stars})"
        )
    return discord.Embed(
        title="🌱 Youth Academy Intake",
        description=header + ("\n".join(lines) if lines else "_No prospects seated._"),
        color=COLOR_GRAY,
    ).set_footer(
        text="Seated in Youth Academy (/development) — not auto-added to your XI."
    )

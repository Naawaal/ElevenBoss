# apps/discord_bot/core/league_announcement.py
"""Season-start announcement helpers (US-28 / 020 League Dynamics)."""
from __future__ import annotations

HUB_CTA = "Check `/league hub` to view standings and play your fixtures."


def build_season_start_message(
    league_name: str,
    season_number: int,
    total_matchdays: int,
    *,
    dynamics: bool = False,
    division_count: int = 1,
) -> str:
    """Plain-text season kickoff body (role ping is added by ``send_league_announcement``)."""
    if not dynamics:
        return (
            f"**{league_name}**: **Season {season_number}** is Live!\n"
            f"{HUB_CTA} (Season Length: **{total_matchdays} Matchdays** )"
        )

    lines = [
        f"**{league_name}**: **Season {season_number}** is Live!",
        HUB_CTA,
        "⏱ **14-day** season — play each matchday **before 00:00 UTC**.",
        "Unplayed fixtures auto-sim shortly after midnight UTC.",
        "🏅 **Manager of the Matchday**: biggest *manual* win that day earns a coin bonus.",
    ]
    if division_count > 1:
        lines.append(f"📊 **{division_count} Seasonal Divisions** — you only play clubs in your division.")
    lines.append(f"(Season Length: **{total_matchdays} Matchdays**)")
    return "\n".join(lines)

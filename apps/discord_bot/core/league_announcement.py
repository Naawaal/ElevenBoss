# apps/discord_bot/core/league_announcement.py
"""Season-start announcement helpers (US-28)."""
from __future__ import annotations

HUB_CTA = "Check `/league hub` to view standings and play your fixtures."


def build_season_start_message(
    league_name: str,
    season_number: int,
    total_matchdays: int,
) -> str:
    """Plain-text season kickoff body (role ping is added by ``send_league_announcement``)."""
    return (
        f"**{league_name}**: **Season {season_number}** is Live!\n"
        f"{HUB_CTA} (Season Length: **{total_matchdays} Matchdays** )"
    )

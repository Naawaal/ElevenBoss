# tests/test_league_announcement.py
"""US-28 season announcement message tests."""
from __future__ import annotations

from apps.discord_bot.core.league_announcement import (
    HUB_CTA,
    build_season_start_message,
)


def test_build_season_start_message_structure():
    body = build_season_start_message("New Anime Hindi", 5, 14)
    assert body.startswith("**New Anime Hindi**: **Season 5** is Live!")
    assert "`/league hub`" in body
    assert "(Season Length: **14 Matchdays** )" in body


def test_hub_cta_constant():
    assert "league hub" in HUB_CTA.lower()
    assert HUB_CTA in build_season_start_message("X", 1, 1)

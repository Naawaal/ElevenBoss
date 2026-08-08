# tests/test_competitive_stadium_presentation.py
"""Feature 057 US5 — stadium tier + scoreline helpers."""
from __future__ import annotations

from types import SimpleNamespace

from apps.discord_bot.core.competitive_match import (
    competitive_result_str,
    event_presentation_tier,
    format_scoreline,
    format_shootout_emoji_line,
)


def test_tier_a_for_goals_and_phase_banners():
    assert event_presentation_tier("GOAL") == "A"
    assert event_presentation_tier("EXTRA_TIME_START") == "A"
    assert event_presentation_tier("PENALTY_KICK") == "A"
    assert event_presentation_tier("CHANCE") == "B"
    assert event_presentation_tier("POSSESSION_START") == "C"


def test_format_scoreline_pens_and_aet():
    pens = SimpleNamespace(
        home_score=2,
        away_score=2,
        decided_by="penalties",
        home_penalties=5,
        away_penalties=4,
        played_extra_time=True,
    )
    assert "pens" in format_scoreline(pens)
    aet = SimpleNamespace(
        home_score=3, away_score=2, decided_by="extra_time", played_extra_time=True,
        home_penalties=0, away_penalties=0,
    )
    assert "AET" in format_scoreline(aet)


def test_competitive_result_uses_pens_winner():
    state = SimpleNamespace(
        home_score=1, away_score=1, decided_by="penalties",
        home_penalties=4, away_penalties=3,
    )
    assert competitive_result_str(state) == "win"


def test_shootout_emoji_line():
    blob = {
        "events": [
            {"club_side": "home", "outcome": "goal"},
            {"club_side": "away", "outcome": "saved"},
        ]
    }
    line = format_shootout_emoji_line(blob)
    assert "H🟢" in line and "A❌" in line

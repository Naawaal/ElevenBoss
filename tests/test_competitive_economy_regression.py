# tests/test_competitive_economy_regression.py
"""Feature 057 — flag-off path and result helpers do not invent parallel pipes."""
from __future__ import annotations

from apps.discord_bot.core.competitive_flags import apply_bot_difficulty_delta
from apps.discord_bot.core.competitive_match import competitive_result_str
from types import SimpleNamespace


def test_difficulty_delta_clamped():
    settings = {"enabled": True, "rating_offset": 0, "min_delta": -4, "max_delta": 4}
    # Manager much stronger → bot nudged up but capped
    out = apply_bot_difficulty_delta(60.0, manager_ovr=90.0, settings=settings)
    assert 60.0 <= out <= 64.0


def test_regulation_result_unchanged_without_pens():
    state = SimpleNamespace(
        home_score=2, away_score=1, decided_by="regulation",
        home_penalties=0, away_penalties=0,
    )
    assert competitive_result_str(state) == "win"
    draw = SimpleNamespace(
        home_score=1, away_score=1, decided_by="regulation",
        home_penalties=0, away_penalties=0,
    )
    assert competitive_result_str(draw) == "draw"

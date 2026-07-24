# tests/test_match_explanation_ui.py
"""Discord tip formatter for V3 post-match explainability (044)."""
from __future__ import annotations

from apps.discord_bot.cogs.battle_cog import explanation_field_value, format_explanation_tip


def test_format_tip_prefers_causal_hint():
    line = format_explanation_tip(
        {"minute": 22, "type": "GOAL", "causal_hint": "build_up finished"}
    )
    assert line == "• 22' — build_up finished"
    assert "GOAL" not in line


def test_format_tip_humanizes_snake_hint():
    line = format_explanation_tip({"minute": 40, "type": "CHANCE", "causal_hint": "chance_pattern"})
    assert line == "• 40' — chance pattern"


def test_explanation_field_headline_only_when_no_tips():
    value = explanation_field_value({"headline": "Honours even after a contested match", "turning_points": []})
    assert value == "Honours even after a contested match"


def test_explanation_field_omits_empty():
    assert explanation_field_value({"headline": "", "turning_points": []}) is None

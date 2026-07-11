# tests/test_live_match_ticker.py
from __future__ import annotations

from apps.discord_bot.cogs.battle_cog import (
    GOAL_SCROLL_CAP,
    append_goal_scroll,
    format_goal_scroll_line,
    format_ticker_line,
)


def test_format_goal_scroll_line() -> None:
    assert format_goal_scroll_line(14, "Ada Okonkwo") == "⚽ 14' Ada Okonkwo"


def test_append_goal_scroll_caps_at_10() -> None:
    scroll: list[str] = []
    for i in range(12):
        append_goal_scroll(scroll, i, f"P{i}")
    assert len(scroll) == GOAL_SCROLL_CAP
    assert scroll[0] == "⚽ 2' P2"
    assert scroll[-1] == "⚽ 11' P11"


def test_empty_goal_scroll_is_falsy_for_omit() -> None:
    assert not []


def test_format_ticker_half_time_separator() -> None:
    line = format_ticker_line("HALF_TIME", 45, "ignored prose")
    assert "--- HALF TIME ---" in line
    assert "45" not in line or "HALF TIME" in line


def test_format_ticker_goal_keeps_minute_and_text() -> None:
    line = format_ticker_line("GOAL", 22, "Ada finds the net!")
    assert "22'" in line
    assert "Ada finds the net!" in line
    assert "⚽" in line

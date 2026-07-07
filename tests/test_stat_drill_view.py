# tests/test_stat_drill_view.py
"""Run Drill button must enable only when player + unlocked drill are chosen."""
from __future__ import annotations

from unittest.mock import patch

from apps.discord_bot.cogs.development_cog import StatDrillView

_MOCK_PLAYERS = [
    {"id": "uuid-low", "name": "Youth Striker", "overall": 62, "level": 5, "position": "FWD"},
    {"id": "uuid-high", "name": "Veteran Mid", "overall": 78, "level": 12, "position": "MID"},
]


def _view() -> StatDrillView:
    return StatDrillView(owner_id=1, eligible_players=_MOCK_PLAYERS)


def test_run_drill_disabled_initially() -> None:
    view = _view()
    assert view.run_btn.disabled is True


def test_run_drill_disabled_with_player_only() -> None:
    view = _view()
    view.selected_card_id = "uuid-low"
    view._build_items()
    assert view.run_btn.disabled is True


def test_run_drill_enabled_with_player_and_drill() -> None:
    view = _view()
    view.selected_card_id = "uuid-low"
    view.selected_drill = "pac_sprint"
    view._build_items()
    assert view.run_btn.disabled is False


def test_run_drill_disabled_when_drill_locked() -> None:
    view = _view()
    view.selected_card_id = "uuid-low"
    view.selected_drill = "pac_sprint"
    with patch("apps.discord_bot.cogs.development_cog.drill_unlocked", return_value=False):
        view._build_items()
    assert view.run_btn.disabled is True

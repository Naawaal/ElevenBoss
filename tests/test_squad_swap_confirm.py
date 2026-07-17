# tests/test_squad_swap_confirm.py
"""Confirm Swap button must enable after both selects are chosen."""
from __future__ import annotations

from apps.discord_bot.cogs.squad_cog import SquadSwapView, _swap_selection_ready


class _FakeHub:
    def __init__(self) -> None:
        self.formation = "4-4-2"
        # Slot 10 = FWD on 4-4-2; reserve must share that band
        self.assignments = {
            10: {"id": "starter-uuid", "name": "Starter", "position": "FWD", "overall": 70},
        }


def test_confirm_disabled_until_both_selected() -> None:
    hub = _FakeHub()
    starters = [hub.assignments[10]]
    reserves = [{"id": "reserve-uuid", "name": "Reserve", "position": "FWD", "overall": 65}]
    view = SquadSwapView(user_id=1, hub_view=hub, starters=starters, reserves=reserves)

    assert view.confirm_btn.disabled is True

    view.selected_starter_id = "starter-uuid"
    view.setup_components()
    assert view.confirm_btn.disabled is True

    view.selected_reserve_id = "reserve-uuid"
    view.setup_components()
    assert view.confirm_btn.disabled is False


def test_swap_selection_ready_rejects_none() -> None:
    assert not _swap_selection_ready("starter-uuid", None)
    assert not _swap_selection_ready("none", "reserve-uuid")

# tests/test_squad_swap_confirm.py
"""Confirm Swap button must enable after both selects are chosen."""
from __future__ import annotations

import json
import time

from apps.discord_bot.cogs.squad_cog import SquadSwapView, _swap_selection_ready

_DEBUG_LOG = "debug-4aa967.log"


def _log(message: str, data: dict) -> None:
    with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "sessionId": "4aa967",
                    "runId": "swap-confirm-test",
                    "hypothesisId": "A",
                    "timestamp": int(time.time() * 1000),
                    "location": "test_squad_swap_confirm.py",
                    "message": message,
                    "data": data,
                }
            )
            + "\n"
        )


class _FakeHub:
    def __init__(self) -> None:
        self.assignments = {
            1: {"id": "starter-uuid", "name": "Starter", "position": "FWD", "overall": 70},
        }


def test_confirm_disabled_until_both_selected() -> None:
    hub = _FakeHub()
    starters = [hub.assignments[1]]
    reserves = [{"id": "reserve-uuid", "name": "Reserve", "position": "MID", "overall": 65}]
    view = SquadSwapView(user_id=1, hub_view=hub, starters=starters, reserves=reserves)

    assert view.confirm_btn.disabled is True
    _log("initial", {"disabled": view.confirm_btn.disabled})

    view.selected_starter_id = "starter-uuid"
    view.setup_components()
    assert view.confirm_btn.disabled is True
    _log("starter only", {"disabled": view.confirm_btn.disabled})

    view.selected_reserve_id = "reserve-uuid"
    view.setup_components()
    assert view.confirm_btn.disabled is False
    _log("both selected", {"disabled": view.confirm_btn.disabled})


def test_swap_selection_ready_rejects_none() -> None:
    assert not _swap_selection_ready("starter-uuid", None)
    assert not _swap_selection_ready("none", "reserve-uuid")

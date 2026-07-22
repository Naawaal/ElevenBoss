"""Tests for US-42.2 action matrix (spec §B.5)."""
from __future__ import annotations

import pytest

from player_engine.card_state import can_perform_action


@pytest.mark.parametrize(
    "primary,match_locked,injury,hospital,action,allowed",
    [
        ("Listed", False, None, False, "drill", False),
        ("Listed", False, None, False, "cancel_listing", True),
        ("Listed", False, None, False, "start_evolution", False),
        ("Listed", False, None, False, "view_profile", True),
        ("RosterFree", False, None, False, "list_transfer", True),
        ("RosterFree", False, 2, False, "list_transfer", False),
        ("RosterFree", False, None, False, "list_transfer", True),
        ("RosterFree", False, None, False, "agent_sell", True),
        ("RosterFree", False, 1, False, "agent_sell", False),
        ("Hospitalized", False, 2, True, "agent_sell", False),
        ("Hospitalized", False, None, True, "drill", False),
        ("Evolving", False, None, False, "start_evolution", False),
        ("Evolving", False, None, False, "claim_evolution", True),
        ("Evolving", False, None, False, "cancel_evolution", True),
        ("Evolving", False, None, False, "assign_xi", True),
        ("Evolving", False, None, False, "match_include", True),
        ("Evolving", False, None, False, "bench", True),
        ("InXI", False, None, False, "start_evolution", True),
        ("InXI", False, None, False, "drill", True),
        ("InXI", False, None, False, "list_transfer", False),
        ("RosterFree", False, None, False, "assign_xi", True),
        ("RosterFree", True, None, False, "assign_xi", False),
        ("RosterFree", True, None, False, "drill", False),
        ("RosterFree", True, None, False, "start_evolution", False),
        ("RosterFree", True, None, False, "list_transfer", False),
        ("Evolving", True, None, False, "claim_evolution", False),
        ("InXI", True, None, False, "view_profile", True),
        ("RosterFree", False, None, False, "view_profile", True),
        # fatigue alone does not block list — modeled by no injury
        ("RosterFree", False, None, False, "list_transfer", True),
        ("InAcademy", False, None, False, "drill", False),
        ("Retired", False, None, False, "drill", False),
        ("SoldTransferred", False, None, False, "view_profile", False),
    ],
)
def test_matrix_cells(primary, match_locked, injury, hospital, action, allowed):
    ok, reason = can_perform_action(
        primary,
        match_locked=match_locked,
        injury_tier=injury,
        in_hospital=hospital,
        action=action,
    )
    assert ok is allowed, (primary, action, reason)
    if allowed:
        assert reason == ""
    else:
        assert reason

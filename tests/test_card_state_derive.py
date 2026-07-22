"""Tests for US-42.2 derive_primary_state / exclusive conflict."""
from __future__ import annotations

import pytest

from player_engine.card_state import (
    CardStateFlags,
    can_perform_action_from_flags,
    derive_primary_state,
    detect_exclusive_conflict,
    has_exclusive_conflict,
)


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, "RosterFree"),
        ({"in_xi": True}, "InXI"),
        ({"listed": True}, "Listed"),
        ({"in_hospital": True}, "Hospitalized"),
        ({"evolving": True}, "Evolving"),
        ({"training_busy": True}, "TrainingBusy"),
        ({"in_academy": True}, "InAcademy"),
        ({"retired": True}, "Retired"),
        ({"owned_by_viewer": False}, "SoldTransferred"),
        ({"retired": True, "listed": True}, "Retired"),  # priority
        ({"listed": True, "in_hospital": True}, "Listed"),  # priority label
    ],
)
def test_derive_primary_state(kwargs, expected):
    assert derive_primary_state(CardStateFlags(**kwargs)) == expected


def test_injury_without_hospital_is_roster_free_not_hospitalized():
    flags = CardStateFlags(injury_tier=2, in_hospital=False)
    assert derive_primary_state(flags) == "RosterFree"
    assert has_exclusive_conflict(flags) is False


def test_hospitalized_not_injury_modifier_primary():
    flags = CardStateFlags(injury_tier=2, in_hospital=True)
    assert derive_primary_state(flags) == "Hospitalized"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"listed": True, "in_hospital": True},
        {"listed": True, "evolving": True},
        {"in_hospital": True, "in_academy": True},
        {"listed": True, "in_xi": True},
        {"retired": True, "in_academy": True},
    ],
)
def test_exclusive_conflict_detected(kwargs):
    flags = CardStateFlags(**kwargs)
    assert has_exclusive_conflict(flags) is True
    assert detect_exclusive_conflict(flags) is not None
    ok, reason = can_perform_action_from_flags(flags, action="drill")
    assert ok is False
    assert reason == "state_conflict"


def test_single_busy_no_conflict():
    flags = CardStateFlags(listed=True)
    assert has_exclusive_conflict(flags) is False
    assert detect_exclusive_conflict(flags) is None


def test_evolving_in_xi_not_conflict_claim_allowed():
    flags = CardStateFlags(evolving=True, in_xi=True)
    assert has_exclusive_conflict(flags) is False
    ok, reason = can_perform_action_from_flags(flags, action="claim_evolution")
    assert ok is True
    assert reason == ""

# tests/test_competitive_recovery.py
"""Feature 057 US3 — competitive snapshot shape + resume classification helpers."""
from __future__ import annotations

from match_engine.competitive_models import MatchPhase, competitive_snapshot, deterministic_sub_seed


def test_sub_seeds_stable():
    assert deterministic_sub_seed(42, "et1") == deterministic_sub_seed(42, "et1")
    assert deterministic_sub_seed(42, "et1") != deterministic_sub_seed(42, "et2")
    assert deterministic_sub_seed(42, "shootout") != deterministic_sub_seed(42, "et1")


def test_competitive_snapshot_fields():
    snap = competitive_snapshot(
        phase=MatchPhase.PENALTY_SHOOTOUT,
        phase_minute=100,
        home_score=1,
        away_score=1,
        decided_by=None,
        penalty_state={"home_kicks_taken": 2},
        home_penalties=1,
        away_penalties=1,
        shootout_seed=99,
    )
    assert snap["match_phase"] == "PENALTY_SHOOTOUT"
    assert snap["penalty_state"]["home_kicks_taken"] == 2
    assert snap["shootout_seed"] == 99

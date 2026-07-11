# tests/test_probability_floor.py
from __future__ import annotations

from match_engine.v2_simulator import _probability_floor


def test_probability_floor_always_five_percent() -> None:
    assert _probability_floor(50.0, 50.0) == 0.05
    assert _probability_floor(99.0, 40.0) == 0.05  # large gap — no 0.02 branch
    assert _probability_floor(40.0, 99.0) == 0.05

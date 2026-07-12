# tests/test_bench_rest_selection.py
"""Pure bench-rest candidate ordering (014)."""
from __future__ import annotations

from player_engine import BENCH_REST_LIMIT, pick_bench_rest_ids


def test_pick_bench_rest_ids_top_overall_cap() -> None:
    starters = [f"s{i}" for i in range(11)]
    unused = [{"id": f"u{i}", "overall": 50 + i, "injury_tier": None} for i in range(10)]
    cards = [{"id": sid, "overall": 70, "injury_tier": None} for sid in starters] + unused
    picked = pick_bench_rest_ids(cards, starters)
    assert len(picked) == BENCH_REST_LIMIT
    assert picked == ["u9", "u8", "u7", "u6", "u5", "u4", "u3"]


def test_pick_bench_rest_ids_skips_injured_and_starters() -> None:
    starters = ["a"]
    cards = [
        {"id": "a", "overall": 99, "injury_tier": None},
        {"id": "b", "overall": 90, "injury_tier": 1},
        {"id": "c", "overall": 80, "injury_tier": None},
        {"id": "d", "overall": 85, "injury_tier": None, "is_retired": True},
        {"id": "e", "overall": 70, "injury_tier": None},
    ]
    assert pick_bench_rest_ids(cards, starters) == ["c", "e"]

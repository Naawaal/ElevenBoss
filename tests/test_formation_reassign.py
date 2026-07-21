# tests/test_formation_reassign.py
"""Formation change should preserve starters; bench only fills gaps."""
from __future__ import annotations

from match_engine import reassign_formation_slots


def _card(card_id: str, position: str, overall: int) -> dict:
    return {"id": card_id, "position": position, "overall": overall, "name": card_id}


def test_reassign_keeps_starters_when_they_still_fit() -> None:
    starters = {
        1: _card("gk", "GK", 70),
        2: _card("lb", "DEF", 72),
        3: _card("cb1", "DEF", 74),
        4: _card("cb2", "DEF", 73),
        5: _card("rb", "DEF", 71),
        6: _card("lm", "MID", 76),
        7: _card("cm1", "MID", 75),
        8: _card("cm2", "MID", 74),
        9: _card("rm", "MID", 73),
        10: _card("st1", "FWD", 78),
        11: _card("st2", "FWD", 77),
    }
    bench = [_card("bench-fwd", "FWD", 90), _card("bench-mid", "MID", 88)]
    all_cards = list(starters.values()) + bench

    result = reassign_formation_slots("4-3-3", starters, all_cards)

    for slot, card in starters.items():
        assert result[slot]["id"] == card["id"]
    assert "bench-fwd" not in {result[s]["id"] for s in result}


def test_reassign_pulls_from_bench_only_for_empty_slots() -> None:
    starters = {
        1: _card("gk", "GK", 70),
        2: _card("lb", "DEF", 72),
        3: _card("cb1", "DEF", 74),
        4: _card("cb2", "DEF", 73),
        5: _card("rb", "DEF", 71),
        6: _card("lm", "MID", 76),
        7: _card("cm1", "MID", 75),
        8: _card("cm2", "MID", 74),
        9: _card("rm", "MID", 73),
        10: _card("st1", "FWD", 78),
        # slot 11 empty after retirement
    }
    bench = [_card("bench-fwd", "FWD", 65)]
    all_cards = list(starters.values()) + bench

    result = reassign_formation_slots("4-4-2", starters, all_cards)

    assert result[11]["id"] == "bench-fwd"
    assert result[10]["id"] == "st1"

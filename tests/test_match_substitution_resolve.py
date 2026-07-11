# tests/test_match_substitution_resolve.py
"""Phase 3 pure substitution / Play On / 10-men helpers."""
from __future__ import annotations

import random
from types import SimpleNamespace

from match_engine.substitution_resolve import (
    MAX_SUBS_PER_MATCH,
    apply_sub,
    apply_ten_men,
    auto_pick_bench,
    auto_resolve_injury,
    emergency_gk_card,
    play_on_tier_upgrade,
)


def _p(name: str, pos: str, ovr: int, cid: str, fatigue: int = 100):
    return SimpleNamespace(
        name=name, position=pos, overall=ovr, card_id=cid, fatigue=fatigue
    )


def test_auto_pick_prefers_same_position_group():
    bench = [
        _p("Mid", "CM", 80, "m1"),
        _p("Def", "CB", 90, "d1"),
    ]
    pick = auto_pick_bench(bench, "LB")
    assert pick.card_id == "d1"


def test_auto_pick_falls_back_to_highest_ovr():
    bench = [
        _p("A", "ST", 70, "a"),
        _p("B", "ST", 85, "b"),
    ]
    pick = auto_pick_bench(bench, "GK")
    assert pick.card_id == "b"


def test_auto_pick_empty():
    assert auto_pick_bench([], "ST") is None


def test_apply_sub_and_ten_men():
    squad = [_p("Inj", "ST", 80, "inj"), _p("Other", "CM", 70, "o")]
    bench = [_p("Sub", "ST", 75, "sub")]
    new_squad, new_bench = apply_sub(squad, bench, "inj", "sub")
    assert {p.card_id for p in new_squad} == {"o", "sub"}
    assert new_bench == []
    ten = apply_ten_men(squad, "inj")
    assert [p.card_id for p in ten] == ["o"]


def test_emergency_gk_picks_highest_outfield():
    squad = [_p("D", "CB", 60, "d"), _p("M", "CM", 80, "m"), _p("G", "GK", 50, "g")]
    em = emergency_gk_card(squad)
    assert em.card_id == "m"


def test_play_on_tier_upgrade_caps_major():
    rng = random.Random(0)
    # Force many rolls; never exceed 3
    for _ in range(50):
        assert play_on_tier_upgrade(3, rng) == 3
    # Seeded: some upgrades from 1
    ups = sum(1 for i in range(100) if play_on_tier_upgrade(1, random.Random(i)) == 2)
    assert 40 <= ups <= 80  # ~60%


def test_auto_resolve_sub_when_bench():
    injured = _p("Inj", "ST", 80, "inj", fatigue=50)
    bench = [_p("Sub", "ST", 75, "sub")]
    squad = [injured, _p("O", "CM", 70, "o")]
    res = auto_resolve_injury(
        side="home",
        injured=injured,
        bench=bench,
        squad=squad,
        subs_used=0,
        tier=1,
    )
    assert res.kind == "sub"
    assert res.replacement_card_id == "sub"


def test_auto_resolve_ten_men_when_no_subs():
    injured = _p("Inj", "ST", 80, "inj")
    res = auto_resolve_injury(
        side="home",
        injured=injured,
        bench=[_p("Sub", "ST", 75, "sub")],
        squad=[injured],
        subs_used=MAX_SUBS_PER_MATCH,
        tier=2,
    )
    assert res.kind == "ten_men"


def test_auto_resolve_gk_emergency():
    injured = _p("GK", "GK", 80, "gk")
    out = _p("CB", "CB", 70, "cb")
    res = auto_resolve_injury(
        side="away",
        injured=injured,
        bench=[],
        squad=[injured, out],
        subs_used=0,
        tier=2,
    )
    assert res.kind == "emergency_gk"
    assert res.replacement_card_id == "cb"

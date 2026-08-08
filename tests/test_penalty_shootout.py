# tests/test_penalty_shootout.py
"""Feature 057 US2 — penalty shootout pure module."""
from __future__ import annotations

from match_engine.penalty_shootout import (
    P_GOAL_MAX,
    P_GOAL_MIN,
    conversion_probability,
    order_penalty_takers,
    pick_goalkeeper,
    run_shootout,
)


def _player(name: str, sho: int, *, pos: str = "ST", defense: int = 50, cons: int = 50):
    return {
        "id": name,
        "name": name,
        "position": pos,
        "sho": sho,
        "overall": sho,
        "def_stat": defense,
        "consistency": cons,
        "fitness": 80,
        "morale": 70,
    }


def test_conversion_probability_clamped():
    weak = _player("W", 40)
    strong_gk = _player("GK", 50, pos="GK", defense=99)
    p = conversion_probability(weak, strong_gk)
    assert P_GOAL_MIN <= p <= P_GOAL_MAX

    ace = _player("A", 99, cons=99)
    soft_gk = _player("G", 40, pos="GK", defense=30)
    p2 = conversion_probability(ace, soft_gk)
    assert P_GOAL_MIN <= p2 <= P_GOAL_MAX


def test_taker_order_prefers_higher_sho():
    players = [_player("Low", 40), _player("High", 90), _player("Mid", 60)]
    import random

    ordered = order_penalty_takers(players, random.Random(1))
    assert ordered[0]["name"] == "High"


def test_shootout_completes_and_deterministic():
    home = [_player(f"H{i}", 60 + i) for i in range(5)]
    away = [_player(f"A{i}", 58 + i) for i in range(5)]
    hg = pick_goalkeeper([_player("HGK", 55, pos="GK", defense=70)] + home)
    ag = pick_goalkeeper([_player("AGK", 55, pos="GK", defense=68)] + away)

    a = run_shootout(
        home_eligible=home, away_eligible=away, home_gk=hg, away_gk=ag, shootout_seed=12345
    )
    b = run_shootout(
        home_eligible=home, away_eligible=away, home_gk=hg, away_gk=ag, shootout_seed=12345
    )
    assert a.completed and b.completed
    assert a.winner_side in ("home", "away")
    assert a.home_penalties_scored == b.home_penalties_scored
    assert a.away_penalties_scored == b.away_penalties_scored
    assert [e.outcome for e in a.events] == [e.outcome for e in b.events]


def test_early_stop_possible():
    # Overwhelming home quality should often finish before all 10 first-round kicks
    home = [_player(f"H{i}", 95, cons=95) for i in range(5)]
    away = [_player(f"A{i}", 35, cons=30) for i in range(5)]
    hg = _player("HGK", 50, pos="GK", defense=40)
    ag = _player("AGK", 50, pos="GK", defense=30)
    finished_early = False
    for seed in range(50):
        s = run_shootout(
            home_eligible=home, away_eligible=away, home_gk=hg, away_gk=ag, shootout_seed=seed
        )
        if s.completed and len(s.events) < 10:
            finished_early = True
            break
    assert finished_early

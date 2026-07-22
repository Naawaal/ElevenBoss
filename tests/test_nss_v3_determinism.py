# tests/test_nss_v3_determinism.py
"""SC-001: Deterministic Replay Digest identity across two silent runs."""
from __future__ import annotations

from match_engine import MatchPlayerCard
from match_engine.v3 import SimulationEngine, deterministic_replay_digest


def _xi(ovr: int = 70) -> list[MatchPlayerCard]:
    roles = ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2
    return [
        MatchPlayerCard(
            name=f"P{i}",
            position=roles[i],
            overall=ovr,
            pac=ovr,
            sho=ovr,
            pas=ovr,
            dri=ovr,
            def_stat=ovr,
            phy=ovr,
            card_id=f"c{i}",
        )
        for i in range(11)
    ]


def test_replay_digest_identical_across_two_runs():
    home, away = _xi(72), _xi(68)
    digests = []
    for _ in range(2):
        eng = SimulationEngine()
        ctx = eng.initial_context(
            home=home,
            away=away,
            home_name="Home FC",
            away_name="Away FC",
            home_rating=72.0,
            away_rating=68.0,
            seed=42,
        )
        ctx2, events = eng.run_to_completion(ctx)
        assert ctx2.terminal or events[-1].type == "FULL_TIME"
        digests.append(deterministic_replay_digest(events))
        digests.append(eng.digests()["replay"])
    assert digests[0] == digests[1] == digests[2] == digests[3]


def test_sporting_digest_stable():
    home, away = _xi(75), _xi(75)
    eng = SimulationEngine()
    ctx = eng.initial_context(
        home=home,
        away=away,
        home_name="A",
        away_name="B",
        home_rating=75.0,
        away_rating=75.0,
        seed=99,
    )
    _, events = eng.run_to_completion(ctx)
    d1 = eng.digests()["sporting"]
    eng2 = SimulationEngine()
    ctx2 = eng2.initial_context(
        home=home,
        away=away,
        home_name="A",
        away_name="B",
        home_rating=75.0,
        away_rating=75.0,
        seed=99,
    )
    eng2.run_to_completion(ctx2)
    assert d1 == eng2.digests()["sporting"]

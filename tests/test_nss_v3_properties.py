# tests/test_nss_v3_properties.py
"""Property checks for NSS v3 event streams."""
from __future__ import annotations

from match_engine import MatchPlayerCard
from match_engine.v3 import SimulationEngine


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
            card_id=f"id{i}",
        )
        for i in range(11)
    ]


def test_seq_monotonic_and_full_time():
    eng = SimulationEngine()
    ctx = eng.initial_context(
        home=_xi(70),
        away=_xi(70),
        home_name="H",
        away_name="A",
        home_rating=70.0,
        away_rating=70.0,
        seed=7,
    )
    _, events = eng.run_to_completion(ctx)
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))
    assert events[0].type == "KICKOFF"
    assert events[-1].type == "FULL_TIME"
    goals = [e for e in events if e.type == "GOAL"]
    # score from state matches GOAL count split is soft — at least FT present
    assert eng._state is not None
    assert eng._state.home_score + eng._state.away_score == len(goals)

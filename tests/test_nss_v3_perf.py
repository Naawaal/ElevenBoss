# tests/test_nss_v3_perf.py
"""Loose CPU budget for silent v3 completion (guidance <50ms typical squad)."""
from __future__ import annotations

import time

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
            card_id=f"p{i}",
        )
        for i in range(11)
    ]


def test_silent_match_under_budget():
    home, away = _xi(72), _xi(70)
    # Warmup
    eng0 = SimulationEngine()
    ctx0 = eng0.initial_context(
        home=home, away=away, home_name="H", away_name="A",
        home_rating=72.0, away_rating=70.0, seed=1,
    )
    eng0.run_to_completion(ctx0)

    t0 = time.perf_counter()
    for seed in range(10):
        eng = SimulationEngine()
        ctx = eng.initial_context(
            home=home, away=away, home_name="H", away_name="A",
            home_rating=72.0, away_rating=70.0, seed=seed,
        )
        eng.run_to_completion(ctx)
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 10
    # Guidance: <50ms mean; allow CI slack
    assert elapsed_ms < 250, f"mean {elapsed_ms:.1f}ms too slow"

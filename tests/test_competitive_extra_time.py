# tests/test_competitive_extra_time.py
"""Feature 057 US1 — competitive extra time on NSS stream."""
from __future__ import annotations

import random

from match_engine.bot_squad import build_bot_match_squad
from match_engine.models import MatchPlayerCard
from match_engine.v2_simulator import MatchState, generate_match_events


def _squad(ovr: int = 70) -> list[MatchPlayerCard]:
    return build_bot_match_squad(ovr, random.Random(42))


def test_flag_off_ends_at_regulation_full_time():
    state = MatchState(home_rating=70, away_rating=70, competitive_enabled=False)
    events = list(generate_match_events(state, _squad(), _squad(71), "Home", "Away", rng=random.Random(1)))
    types = [e["type"] for e in events]
    assert "FULL_TIME" in types
    assert "EXTRA_TIME_START" not in types
    assert state.decided_by == "regulation"
    assert state.minute == 90


def test_competitive_draw_enters_extra_time():
    # Search seeds until regulation is drawn (flag on → ET)
    for seed in range(1, 400):
        state = MatchState(
            home_rating=70,
            away_rating=70,
            competitive_enabled=True,
            sim_seed=seed,
        )
        events = list(
            generate_match_events(
                state, _squad(), _squad(), "Home", "Away", rng=random.Random(seed)
            )
        )
        types = [e["type"] for e in events]
        if "EXTRA_TIME_START" in types:
            assert state.played_extra_time is True
            assert "FULL_TIME" in types
            assert state.decided_by in ("extra_time", "penalties")
            assert state.minute >= 95
            return
    raise AssertionError("no drawn regulation found in seed scan")


def test_same_seed_deterministic_with_competitive():
    def run(seed: int):
        state = MatchState(
            home_rating=72, away_rating=72, competitive_enabled=True, sim_seed=seed
        )
        events = list(
            generate_match_events(
                state, _squad(72), _squad(72), "A", "B", rng=random.Random(seed)
            )
        )
        return (
            [(e["minute"], e["type"], e.get("actor")) for e in events],
            state.home_score,
            state.away_score,
            state.decided_by,
            state.home_penalties,
            state.away_penalties,
        )

    a = run(99)
    b = run(99)
    assert a == b

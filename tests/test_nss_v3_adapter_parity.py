# tests/test_nss_v3_adapter_parity.py
"""US2: async stream adapter vs silent run_to_completion share digests."""
from __future__ import annotations

import asyncio

from match_engine import MatchPlayerCard, MatchState
from match_engine.v3 import (
    SimulationEngine,
    collect_match_events_v3,
    deterministic_replay_digest,
    sporting_digest,
    stream_match_v3,
)
from match_engine.v3.events import from_compat_dict


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
            card_id=f"a{i}",
        )
        for i in range(11)
    ]


async def _stream_digest(seed: int = 11) -> tuple[str, str]:
    home, away = _xi(71), _xi(69)
    state = MatchState(home_rating=71.0, away_rating=69.0)
    state.interactive_sides = []
    compat = []
    async for ev in stream_match_v3(
        state, home, away, "H", "A", sim_seed=seed
    ):
        compat.append(ev)
    events = [
        from_compat_dict(e, seq=i + 1) for i, e in enumerate(compat)
    ]
    return (
        sporting_digest(events, home_score=state.home_score, away_score=state.away_score),
        deterministic_replay_digest(events),
    )


def test_stream_vs_collect_digest_parity():
    async def _run():
        home, away = _xi(71), _xi(69)
        state = MatchState(home_rating=71.0, away_rating=69.0)
        state.interactive_sides = []
        _, _, canon = await collect_match_events_v3(
            state, home, away, "H", "A", 11
        )
        stream_s, stream_r = await _stream_digest(11)
        return (
            sporting_digest(canon, home_score=state.home_score, away_score=state.away_score),
            deterministic_replay_digest(canon),
            stream_s,
            stream_r,
        )

    cs, cr, ss, sr = asyncio.run(_run())
    assert cs == ss
    assert cr == sr


def test_engine_run_matches_collect():
    async def _run():
        home, away = _xi(70), _xi(70)
        eng = SimulationEngine()
        ctx = eng.initial_context(
            home=home,
            away=away,
            home_name="H",
            away_name="A",
            home_rating=70.0,
            away_rating=70.0,
            seed=5,
        )
        _, events = eng.run_to_completion(ctx)
        state = MatchState(home_rating=70.0, away_rating=70.0)
        _, _, canon = await collect_match_events_v3(state, home, away, "H", "A", 5)
        assert eng._state is not None
        return (
            sporting_digest(
                events, home_score=eng._state.home_score, away_score=eng._state.away_score
            ),
            sporting_digest(
                canon, home_score=state.home_score, away_score=state.away_score
            ),
        )

    d1, d2 = asyncio.run(_run())
    assert d1 == d2

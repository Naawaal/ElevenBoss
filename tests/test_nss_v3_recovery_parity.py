# tests/test_nss_v3_recovery_parity.py
"""SC-002: interrupted-path completion matches clean silent replay."""
from __future__ import annotations

import asyncio

from match_engine import MatchPlayerCard, MatchState
from match_engine.v3 import (
    SimulationEngine,
    collect_match_events_v3,
    deterministic_replay_digest,
    sporting_digest,
)


def _xi(ovr: int, tag: str) -> list[MatchPlayerCard]:
    roles = ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2
    return [
        MatchPlayerCard(
            name=f"{tag}{i}",
            position=roles[i],
            overall=ovr,
            pac=ovr,
            sho=ovr,
            pas=ovr,
            dri=ovr,
            def_stat=ovr,
            phy=ovr,
            card_id=f"{tag}-{i}",
        )
        for i in range(11)
    ]


def test_recovery_run_matches_clean_silent():
    """Recovery uses run_to_completion; clean path uses collect_match_events_v3."""

    async def _run():
        home, away = _xi(74, "H"), _xi(70, "A")
        seed = 4242

        clean_state = MatchState(home_rating=74.0, away_rating=70.0)
        clean_state.interactive_sides = []
        _, _, clean_events = await collect_match_events_v3(
            clean_state, home, away, "Home", "Away", seed
        )

        eng = SimulationEngine()
        ctx = eng.initial_context(
            home=home,
            away=away,
            home_name="Home",
            away_name="Away",
            home_rating=74.0,
            away_rating=70.0,
            seed=seed,
        )
        ctx2, recovery_events = eng.run_to_completion(ctx, auto_resolve_injuries=True)
        assert eng._state is not None
        assert ctx2.terminal

        assert clean_state.home_score == eng._state.home_score
        assert clean_state.away_score == eng._state.away_score
        assert sporting_digest(
            clean_events,
            home_score=clean_state.home_score,
            away_score=clean_state.away_score,
        ) == sporting_digest(
            recovery_events,
            home_score=eng._state.home_score,
            away_score=eng._state.away_score,
        )
        assert deterministic_replay_digest(clean_events) == deterministic_replay_digest(
            recovery_events
        )

    asyncio.run(_run())


def test_second_silent_completion_is_idempotent_digest():
    """Settle-once sporting view: replaying the same pin does not drift."""

    async def _run():
        home, away = _xi(68, "H"), _xi(72, "A")
        digests = []
        scores = []
        for _ in range(2):
            state = MatchState(home_rating=68.0, away_rating=72.0)
            _, _, events = await collect_match_events_v3(
                state, home, away, "Home", "Away", 9090
            )
            digests.append(
                sporting_digest(
                    events, home_score=state.home_score, away_score=state.away_score
                )
            )
            scores.append((state.home_score, state.away_score))
        assert digests[0] == digests[1]
        assert scores[0] == scores[1]

    asyncio.run(_run())

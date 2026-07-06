"""Match engine determinism for restart recovery."""
from __future__ import annotations

import asyncio

from match_engine import MatchPlayerCard, MatchState, collect_match_events


def _dummy_squad(rating: int) -> list[MatchPlayerCard]:
    return [
        MatchPlayerCard(name="A", position="FWD", overall=rating),
        MatchPlayerCard(name="B", position="MID", overall=rating),
        MatchPlayerCard(name="C", position="DEF", overall=rating),
    ]


def test_collect_match_events_is_deterministic() -> None:
    async def _run(seed: int) -> tuple[int, int]:
        state = MatchState(home_rating=75.0, away_rating=72.0)
        state, _ = await collect_match_events(
            state,
            _dummy_squad(75),
            _dummy_squad(72),
            "Home FC",
            "Away FC",
            seed,
        )
        return state.home_score, state.away_score

    a = asyncio.run(_run(424242))
    b = asyncio.run(_run(424242))
    assert a == b
    assert 0 <= a[0] <= 15 and 0 <= a[1] <= 15

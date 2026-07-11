# tests/test_nss_win_rates.py
"""Win-rate gates and post-match stat integrity for NSS."""
from __future__ import annotations

import asyncio
import random

import pytest

from match_engine import MatchPlayerCard, MatchState, stream_match, stats_from_events


def _squad11(ovr: int, prefix: str = "P") -> list[MatchPlayerCard]:
    positions = [
        ("GK", f"{prefix} GK"),
        ("DEF", f"{prefix} CB1"),
        ("DEF", f"{prefix} CB2"),
        ("DEF", f"{prefix} LB"),
        ("DEF", f"{prefix} RB"),
        ("MID", f"{prefix} CM1"),
        ("MID", f"{prefix} CM2"),
        ("MID", f"{prefix} CAM"),
        ("FWD", f"{prefix} LW"),
        ("FWD", f"{prefix} RW"),
        ("FWD", f"{prefix} ST"),
    ]
    return [
        MatchPlayerCard(name=name, position=pos, overall=ovr + (i % 3 - 1))
        for i, (pos, name) in enumerate(positions)
    ]


async def _run_n(home_ovr: int, away_ovr: int, n: int) -> tuple[float, float, float]:
    hw = aw = d = 0
    for _ in range(n):
        state = MatchState(home_rating=float(home_ovr), away_rating=float(away_ovr))
        async for _ in stream_match(
            state, _squad11(home_ovr, "H"), _squad11(away_ovr, "A"), "Home", "Away"
        ):
            pass
        if state.home_score > state.away_score:
            hw += 1
        elif state.away_score > state.home_score:
            aw += 1
        else:
            d += 1
    return hw / n, aw / n, d / n


def test_heavy_favorite_wins_99_vs_50() -> None:
    hw, aw, _ = asyncio.run(_run_n(99, 50, 200))
    assert aw < 0.01
    assert hw >= 0.99


def test_moderate_favorite_85_vs_75() -> None:
    hw, _, dr = asyncio.run(_run_n(85, 75, 500))
    assert hw >= 0.75, f"home win rate {hw:.1%} below 75% gate"
    assert dr <= 0.25


def test_even_match_home_win_band() -> None:
    hw, aw, _ = asyncio.run(_run_n(80, 80, 500))
    assert 0.30 <= hw <= 0.50, f"home win {hw:.1%} outside 30-50%"
    assert 0.30 <= aw <= 0.50, f"away win {aw:.1%} outside 30-50%"


def test_post_match_stats_match_events() -> None:
    async def _one() -> None:
        state = MatchState(home_rating=80.0, away_rating=75.0)
        events = []
        async for ev in stream_match(
            state, _squad11(80), _squad11(75), "Home", "Away"
        ):
            events.append(ev)
        rebuilt = stats_from_events(events, "Home")
        assert state.live_stats.home_shots == rebuilt.home_shots
        assert state.live_stats.away_shots == rebuilt.away_shots
        assert state.live_stats.possession_home_pct() + state.live_stats.possession_away_pct() == 100

    asyncio.run(_one())


def test_individual_sho_affects_conversion() -> None:
    """Higher SHO in attack zone should yield more goals over many sims."""

    async def _goals(sho: int, n: int = 150) -> float:
        squad = _squad11(75, "T")
        high_sho = [
            MatchPlayerCard(
                name=p.name, position=p.position, overall=p.overall,
                sho=sho if p.position == "FWD" else p.sho,
            )
            for p in squad
        ]
        total = 0
        for _ in range(n):
            state = MatchState(home_rating=75.0, away_rating=70.0)
            async for _ in stream_match(state, high_sho, _squad11(70, "O"), "Home", "Away"):
                pass
            total += state.home_score
        return total / n

    low = asyncio.run(_goals(50))
    high = asyncio.run(_goals(95))
    assert high >= low, f"high SHO avg goals {high} should be >= low SHO {low}"


def test_no_exact_zero_hundred_possession_batch() -> None:
    """Transition floor + softer midfield momentum: no exact 0–100 possession."""

    async def _run() -> tuple[int, int, int]:
        zero_splits = 0
        favorite_wins = 0
        n = 24
        for i in range(n):
            state = MatchState(home_rating=78.0, away_rating=84.0)
            async for _ in stream_match(
                state,
                _squad11(78, "W"),
                _squad11(84, "S"),
                "Weak",
                "Strong",
                rng=random.Random(1000 + i),
            ):
                pass
            ph = state.live_stats.possession_home_pct()
            pa = state.live_stats.possession_away_pct()
            if (ph, pa) in ((0, 100), (100, 0)):
                zero_splits += 1
            if state.away_score > state.home_score:
                favorite_wins += 1
        return zero_splits, favorite_wins, n

    zero_splits, favorite_wins, n = asyncio.run(_run())
    assert zero_splits == 0, f"{zero_splits} matches had exact 0–100 possession"
    assert favorite_wins >= n // 2, f"favorite wins {favorite_wins}/{n} too low"

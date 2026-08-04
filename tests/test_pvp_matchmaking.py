# tests/test_pvp_matchmaking.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pvp.matchmaking import (
    best_opponent,
    eligible_pair,
    pair_blocked,
    search_range_for_wait,
    sorted_lock_order,
)
from pvp.models import QueueCandidate


def _c(
    owner: int,
    *,
    guild: int = 1,
    div_rank: int = 2,
    lp: int = 1400,
    ovr: float = 82.0,
    joined_ago: float = 5.0,
) -> QueueCandidate:
    now = datetime.now(timezone.utc)
    return QueueCandidate(
        owner_id=owner,
        guild_id=guild,
        global_division="Professional",
        division_rank=div_rank,
        global_lp=lp,
        xi_rating=ovr,
        joined_at=now - timedelta(seconds=joined_ago),
    )


def test_widening_steps() -> None:
    assert search_range_for_wait(0).max_division_delta == 0
    assert search_range_for_wait(20).max_lp_delta == 200
    assert search_range_for_wait(45).max_division_delta == 2
    assert search_range_for_wait(90).max_lp_delta == 500


def test_guild_mismatch_rejected() -> None:
    a, b = _c(1, guild=1), _c(2, guild=2)
    assert not eligible_pair(a, b)


def test_same_guild_in_band() -> None:
    a, b = _c(1, lp=1400), _c(2, lp=1350)
    assert eligible_pair(a, b)


def test_block_both_directions() -> None:
    assert pair_blocked(1, 2, {(1, 2)})
    assert pair_blocked(1, 2, {(2, 1)})
    a, b = _c(1), _c(2)
    assert not eligible_pair(a, b, blocks={(1, 2)})


def test_daily_caps() -> None:
    a, b = _c(1), _c(2)
    assert not eligible_pair(a, b, a_matches_today=5)
    assert not eligible_pair(a, b, pair_matches_today=2)


def test_best_opponent_prefers_closer_lp() -> None:
    seeker = _c(1, lp=1400, joined_ago=40)
    near = _c(2, lp=1410, joined_ago=40)
    far = _c(3, lp=1600, joined_ago=40)
    # far may still be in ±350 at 40s — pick nearer
    pick = best_opponent(seeker, [far, near])
    assert pick is not None
    assert pick.owner_id == 2


def test_sorted_lock_order() -> None:
    assert sorted_lock_order(99, 10) == (10, 99)


def test_pair_blocked_helper_symmetric() -> None:
    """US6: block either direction excludes the pair (matcher + Friendly gate share this)."""
    blocks = {(10, 20)}
    assert pair_blocked(10, 20, blocks)
    assert pair_blocked(20, 10, blocks)
    assert not pair_blocked(10, 30, blocks)

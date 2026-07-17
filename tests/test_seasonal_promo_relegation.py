# tests/test_seasonal_promo_relegation.py
from __future__ import annotations

from leagues.seasonal_divisions import (
    compute_fixed_promo_relegation,
    seat_humans_into_divisions,
)


def test_seat_overflow_to_div2() -> None:
    humans = list(range(1, 10))  # 9 humans
    tiers = seat_humans_into_divisions(humans, clubs_per_div=8)
    assert len(tiers) == 2
    assert tiers[0] == list(range(1, 9))
    assert tiers[1] == [9]


def test_seat_exactly_eight_one_tier() -> None:
    assert seat_humans_into_divisions(list(range(8))) == [list(range(8))]


def test_fixed_promo_top_bottom_two() -> None:
    # best → worst
    table = [10, 20, 30, 40, 50, 60, 70, 80]
    r = compute_fixed_promo_relegation(table, spots=2)
    assert r.promoted_ids == [10, 20]
    assert r.relegated_ids == [70, 80]
    assert r.retained_ids == [30, 40, 50, 60]


def test_n_lt_4_noop() -> None:
    r = compute_fixed_promo_relegation([1, 2, 3], spots=2)
    assert r.promoted_ids == []
    assert r.relegated_ids == []
    assert r.retained_ids == [1, 2, 3]

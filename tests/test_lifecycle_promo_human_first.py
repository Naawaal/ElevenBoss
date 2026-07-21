# tests/test_lifecycle_promo_human_first.py
from __future__ import annotations

from leagues.seasonal_divisions import compute_human_first_promo_relegation


def test_eight_humans_two_up_two_down():
    humans = list(range(1, 9))  # 1 best … 8 worst
    r = compute_human_first_promo_relegation(humans, spots=2)
    assert r.champion_id == 1
    assert r.promoted_ids == [1, 2]
    assert r.relegated_ids == [7, 8]
    assert not (set(r.promoted_ids) & set(r.relegated_ids))


def test_reduce_movement_when_few_humans():
    r = compute_human_first_promo_relegation([10, 20, 30], spots=2)
    assert r.promoted_ids == []
    assert r.relegated_ids == []
    assert r.champion_id == 10


def test_eligible_filter_skips_ineligible_for_promo_slots():
    # 1 is ineligible (e.g. only double_forfeits) — next humans take promo
    ranked = [1, 2, 3, 4, 5, 6, 7, 8]
    r = compute_human_first_promo_relegation(
        ranked, spots=2, eligible_ids=[2, 3, 4, 5, 6, 7, 8]
    )
    assert r.promoted_ids == [2, 3]
    assert 1 not in r.promoted_ids

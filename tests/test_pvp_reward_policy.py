# tests/test_pvp_reward_policy.py
from __future__ import annotations

import pytest

from pvp.reward_policy import (
    assert_lp_allowed,
    practice_lp_delta,
    pvp_lp_delta,
    reward_policy,
)


def test_only_pvp_flags_rivalry_and_record() -> None:
    pvp = reward_policy("pvp", "win")
    assert pvp.rivalry_counted is True
    assert pvp.updates_pvp_record is True
    assert pvp.coin_multiplier == 1.25

    prac = reward_policy("practice", "win", is_new_manager=True)
    assert prac.global_lp_delta == 0
    assert prac.rivalry_counted is False
    assert prac.updates_pvp_record is False
    assert prac.coin_multiplier == 0.75

    est = reward_policy("practice", "loss", is_new_manager=False)
    assert est.coin_multiplier == 0.50

    fri = reward_policy("friendly", "win")
    assert fri.coin_multiplier == 0.0
    assert fri.rivalry_counted is False


def test_practice_lp_always_zero() -> None:
    assert practice_lp_delta() == 0


def test_assert_lp_rejects_practice() -> None:
    with pytest.raises(ValueError):
        assert_lp_allowed("practice", 5)
    assert_lp_allowed("pvp", 15)
    assert_lp_allowed("practice", 0)


def test_provisional_loss_reduced() -> None:
    # base loss -10 → provisional -5
    new_lp, delta = pvp_lp_delta("loss", current_lp=100, ranked_matches_completed=0)
    assert delta == -5
    assert new_lp == 95
    _, full = pvp_lp_delta("loss", current_lp=100, ranked_matches_completed=10)
    assert full == -10

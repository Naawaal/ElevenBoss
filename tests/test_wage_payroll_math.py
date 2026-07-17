# tests/test_wage_payroll_math.py
"""Pure math for weekly wages, strikes, and contract grace (019)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from economy.config import GameConfig
from economy.engine import calculate_weekly_wages
from economy.wages import (
    DEFAULT_CONTRACT_GRACE_DAYS,
    card_weekly_wage,
    calculate_xi_weekly_bill,
    contract_blocks_xi,
    contract_in_grace,
    payroll_outcome_after_pay,
    strike_blocks_friendly,
    strike_blocks_market,
)


def test_ovr_base_wage_common():
    # (70-40)^2 * 1.2 + 10 = 900*1.2 + 10 = 1090
    assert card_weekly_wage({"overall": 70, "rarity": "Common"}) == 1090


def test_calculate_weekly_wages_matches_legacy_common():
    squad = [{"overall": 70, "rarity": "Common"}, {"overall": 60, "rarity": "Common"}]
    cfg = GameConfig()
    assert calculate_weekly_wages(squad, cfg) == calculate_xi_weekly_bill(squad)


def test_bill_scale_halves():
    squad = [{"overall": 70, "rarity": "Common"}]
    full = calculate_xi_weekly_bill(squad, bill_scale=1.0)
    half = calculate_xi_weekly_bill(squad, bill_scale=0.5)
    assert half == int(full * 0.5)


def test_rarity_mult_legendary_higher():
    common = card_weekly_wage({"overall": 70, "rarity": "Common"})
    legendary = card_weekly_wage({"overall": 70, "rarity": "Legendary"})
    assert legendary > common


def test_strike_thresholds():
    assert not strike_blocks_friendly(1)
    assert strike_blocks_friendly(2)
    assert not strike_blocks_market(2)
    assert strike_blocks_market(3)


def test_grace_and_block_windows():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    expires = now - timedelta(days=1)
    assert contract_in_grace(expires, now, grace_days=DEFAULT_CONTRACT_GRACE_DAYS)
    assert not contract_blocks_xi(expires, now, grace_days=7)

    past = now - timedelta(days=10)
    assert not contract_in_grace(past, now, grace_days=7)
    assert contract_blocks_xi(past, now, grace_days=7)

    future = now + timedelta(days=3)
    assert not contract_in_grace(future, now)
    assert not contract_blocks_xi(future, now)


def test_payroll_debt_first_and_strike_reset():
    partial = payroll_outcome_after_pay(coins=100, debt_before=50, bill=200, strikes_before=0)
    assert partial["paid_coins"] == 100
    assert partial["debt_after"] == 150
    assert partial["strikes_after"] == 1

    second = payroll_outcome_after_pay(coins=50, debt_before=150, bill=200, strikes_before=1)
    assert second["strikes_after"] == 2

    clean = payroll_outcome_after_pay(coins=1000, debt_before=50, bill=200, strikes_before=2)
    assert clean["paid_coins"] == 250
    assert clean["debt_after"] == 0
    assert clean["strikes_after"] == 0

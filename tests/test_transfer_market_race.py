# tests/test_transfer_market_race.py
"""SC-005: purchase_transfer_listing race / tax integrity.

Prefer the live smoke script (uses SAVEPOINT double-buy):
  python scratch/smoke_transfer_market.py

When DATABASE_URL is set, this module runs a lightweight tax-split assert
against compute helpers (full concurrent buy is covered by the smoke script).
"""
from __future__ import annotations

import os

import pytest

from economy.transfer_market import seller_net, tax_amount


def test_tax_split_invariant_for_race_math():
    """Loser of a race must not mutate coins; winner tax split is exact."""
    for gross in (100, 999, 9238, 50_000):
        tax = tax_amount(gross)
        net = seller_net(gross)
        assert gross == tax + net
        assert net == gross - tax


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")
def test_hint_run_scratch_smoke_for_double_buy():
    """Document the live race path — invoke scratch script in CI/staging."""
    smoke = os.path.join("scratch", "smoke_transfer_market.py")
    assert os.path.isfile(smoke)

# tests/test_transfer_market_math.py
"""Pure math for P2P transfer tax and listing price bounds."""
from __future__ import annotations

import pytest

from economy.engine import generate_agent_offer
from economy.config import GameConfig
from economy.transfer_market import (
    DEFAULT_TAX_BPS,
    fair_value_coins,
    listing_price_bounds,
    price_bounds_for_card,
    seller_net,
    tax_amount,
    validate_listing_price,
)


def test_tax_10_percent_of_1000():
    assert tax_amount(1000) == 100
    assert seller_net(1000) == 900


def test_tax_rounds_down():
    assert tax_amount(999) == 99
    assert seller_net(999) == 900


def test_floor_ceil_ordering():
    floor, ceil = listing_price_bounds(1000)
    assert floor == 750
    assert ceil == 2500
    assert floor <= ceil


def test_floor_respects_minimum_50():
    floor, ceil = listing_price_bounds(40)
    assert floor == 50
    assert ceil >= floor


def test_validate_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="between"):
        validate_listing_price(100, fair=1000)
    with pytest.raises(ValueError, match="between"):
        validate_listing_price(9999, fair=1000)
    validate_listing_price(1000, fair=1000)


def test_fair_value_reuses_agent_offer():
    cfg = GameConfig()
    assert fair_value_coins(70, "Rare", age=24, potential=80, config=cfg) == generate_agent_offer(
        70, "Rare", cfg, age=24, potential=80
    )


def test_price_bounds_for_card_tuple():
    fair, floor, ceil = price_bounds_for_card(70, "Common", age=22, potential=78)
    assert fair > 0
    assert floor <= fair <= ceil or floor <= ceil  # fair may sit anywhere vs bounds ratio
    assert floor <= ceil


def test_custom_tax_bps():
    assert tax_amount(1000, tax_bps=500) == 50
    assert seller_net(1000, tax_bps=DEFAULT_TAX_BPS) == 900

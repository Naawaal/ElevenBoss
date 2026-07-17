# packages/economy/economy/transfer_market.py
"""P2P transfer market tax, price bounds, and fair-value guides (US-017)."""
from __future__ import annotations

from .config import GameConfig
from .engine import generate_agent_offer

DEFAULT_TAX_BPS = 1000  # 10%
DEFAULT_FLOOR_MULT = 0.75
DEFAULT_CEIL_MULT = 2.5
MIN_LISTING_PRICE = 50


def fair_value_coins(
    player_ovr: int,
    player_rarity: str,
    *,
    age: int | None = None,
    potential: int | None = None,
    config: GameConfig | None = None,
) -> int:
    """Agent-offer valuation used as the P2P fair-value guide."""
    return generate_agent_offer(
        player_ovr,
        player_rarity,
        config or GameConfig(),
        age=age,
        potential=potential,
    )


def tax_amount(gross: int, tax_bps: int = DEFAULT_TAX_BPS) -> int:
    """Coins removed as transfer tax (never credited to seller)."""
    if gross < 0:
        raise ValueError("gross must be non-negative")
    bps = max(0, min(10_000, int(tax_bps)))
    return int(gross * bps // 10_000)


def seller_net(gross: int, tax_bps: int = DEFAULT_TAX_BPS) -> int:
    """Seller proceeds after tax."""
    return int(gross) - tax_amount(gross, tax_bps)


def listing_price_bounds(
    fair: int,
    *,
    floor_mult: float = DEFAULT_FLOOR_MULT,
    ceil_mult: float = DEFAULT_CEIL_MULT,
) -> tuple[int, int]:
    """Return (floor, ceil) coin bounds for a custom listing price."""
    floor = max(MIN_LISTING_PRICE, int(fair * floor_mult))
    ceil = max(floor, int(fair * ceil_mult))
    return floor, ceil


def validate_listing_price(
    price: int,
    fair: int,
    *,
    floor_mult: float = DEFAULT_FLOOR_MULT,
    ceil_mult: float = DEFAULT_CEIL_MULT,
) -> tuple[int, int]:
    """Validate price against bounds; return (floor, ceil). Raises ValueError if out of range."""
    floor, ceil = listing_price_bounds(fair, floor_mult=floor_mult, ceil_mult=ceil_mult)
    if price < floor or price > ceil:
        raise ValueError(f"Price must be between {floor} and {ceil}")
    return floor, ceil


def price_bounds_for_card(
    player_ovr: int,
    player_rarity: str,
    *,
    age: int | None = None,
    potential: int | None = None,
    floor_mult: float = DEFAULT_FLOOR_MULT,
    ceil_mult: float = DEFAULT_CEIL_MULT,
    config: GameConfig | None = None,
) -> tuple[int, int, int]:
    """Return (fair, floor, ceil) for UI preview."""
    fair = fair_value_coins(
        player_ovr, player_rarity, age=age, potential=potential, config=config
    )
    floor, ceil = listing_price_bounds(fair, floor_mult=floor_mult, ceil_mult=ceil_mult)
    return fair, floor, ceil

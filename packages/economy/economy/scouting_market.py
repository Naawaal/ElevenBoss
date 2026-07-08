# packages/economy/economy/scouting_market.py
"""Scouting pool list/purchase pricing (Phase D)."""
from __future__ import annotations

from .config import GameConfig
from .engine import generate_agent_offer


def scouting_purchase_price(
    player_ovr: int,
    player_rarity: str,
    config: GameConfig | None = None,
    *,
    age: int | None = None,
    potential: int | None = None,
) -> int:
    """Coins to sign a scouting pool player (~40% premium over agent sale valuation)."""
    cfg = config or GameConfig()
    base = generate_agent_offer(player_ovr, player_rarity, cfg, age=age, potential=potential)
    return max(100, int(base * 1.4))

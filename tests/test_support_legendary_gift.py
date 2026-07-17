# tests/test_support_legendary_gift.py
"""Pure checks for thank-you Legendary generator (067)."""
from __future__ import annotations

import random

from gacha import generate_support_legendary


def test_generate_support_legendary_bounds() -> None:
    rng = random.Random(42)
    for _ in range(30):
        card = generate_support_legendary(rng=rng)
        assert card.rarity == "Legendary"
        assert 75 <= card.overall <= 85
        assert 90 <= card.potential <= 95
        assert card.potential >= card.overall
        assert card.position in {"GK", "DEF", "MID", "FWD"}
        assert 16 <= card.age <= 23
        assert card.name

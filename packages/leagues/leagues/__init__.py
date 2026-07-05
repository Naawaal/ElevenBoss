# packages/leagues/leagues/__init__.py
from __future__ import annotations

from .models import LeagueEntry, PromotionResult
from .calculator import compute_promotions_relegations

__all__ = [
    "LeagueEntry",
    "PromotionResult",
    "compute_promotions_relegations",
]

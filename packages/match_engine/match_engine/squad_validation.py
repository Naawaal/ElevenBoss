# packages/match_engine/match_engine/squad_validation.py
"""Squad lineup validation helpers (pure logic)."""
from __future__ import annotations

from .formation_positions import get_slot_role


def reserve_fits_formation_slot(formation: str, slot: int, position: str) -> bool:
    """Return True when a reserve's broad position matches the formation slot role."""
    return position == get_slot_role(formation, slot)

# packages/energy/energy/__init__.py
from __future__ import annotations

from .models import EnergyStatus
from .calculator import apply_regen_tick, ticks_to_full, minutes_to_full
from .near_full import is_energy_near_full, near_full_reason

__all__ = [
    "EnergyStatus",
    "apply_regen_tick",
    "ticks_to_full",
    "minutes_to_full",
    "is_energy_near_full",
    "near_full_reason",
]

# packages/energy/energy/calculator.py
from __future__ import annotations
import math

def apply_regen_tick(current: int, max_energy: int, regen_per_tick: int = 2) -> int:
    """Regenerates energy by a tick amount, capped at max_energy."""
    if current >= max_energy:
        return max_energy
    return min(current + regen_per_tick, max_energy)

def ticks_to_full(current: int, max_energy: int, regen_per_tick: int = 2) -> int:
    """Calculates how many ticks are needed to reach max_energy."""
    if current >= max_energy:
        return 0
    needed = max_energy - current
    return math.ceil(needed / regen_per_tick)

def minutes_to_full(current: int, max_energy: int, regen_per_tick: int = 2, minutes_per_tick: int = 5) -> int:
    """Calculates how many minutes are needed to reach max_energy."""
    ticks = ticks_to_full(current, max_energy, regen_per_tick)
    return ticks * minutes_per_tick

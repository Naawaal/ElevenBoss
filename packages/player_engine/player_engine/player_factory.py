# packages/player_engine/player_engine/player_factory.py
"""Unified procedural player creation for gacha / intake sources."""
from __future__ import annotations

import math
import random
from datetime import date

from .age_manager import dob_from_age
from .archetypes import ArchetypeDef, roll_archetype
from .created_card import CreatedPlayerCard
from .engine import calculate_true_ovr
from .potential import generate_potential

_ATTRS = ("pac", "sho", "pas", "dri", "def", "phy")
_STAT_MIN = 10
_STAT_MAX = 99


def roll_creation_age(rng: random.Random | None = None) -> int:
    r = rng or random
    roll = r.random()
    if roll < 0.40:
        return r.randint(16, 21)
    if roll < 0.80:
        return r.randint(22, 27)
    if roll < 0.95:
        return r.randint(28, 32)
    return r.randint(33, 36)


def _clamp(v: int) -> int:
    return max(_STAT_MIN, min(_STAT_MAX, v))


def _ranked_attrs(weights: dict[str, float], *, for_raise: bool) -> list[str]:
    """Attrs with positive weight, sorted primary-first (raise) or secondary-first (lower)."""
    items = [(a, w) for a, w in weights.items() if w > 0]
    items.sort(key=lambda x: x[1], reverse=for_raise)
    return [a for a, _ in items]


def _apply_delta(stats: dict[str, int], attr: str, delta: int) -> bool:
    """Apply ±delta to attr if within bounds. Returns True if any change applied."""
    before = stats[attr]
    stats[attr] = _clamp(before + delta)
    return stats[attr] != before


def balance_true_ovr(
    position: str,
    stats: dict[str, int],
    *,
    target_ovr: int,
    potential: int,
    weights: dict[str, float],
) -> int:
    """Deterministic terminating OVR correction (bulk estimate + greedy ±1)."""
    current = calculate_true_ovr(position, stats, [], potential)
    if current == target_ovr:
        return current

    ranked_up = _ranked_attrs(weights, for_raise=True)
    ranked_down = _ranked_attrs(weights, for_raise=False)
    if not ranked_up:
        return current

    # Bulk jump toward target using top weight as step estimate
    top_w = max(weights.get(a, 0.0) for a in ranked_up) or 0.01
    gap = target_ovr - current
    bulk = max(1, math.ceil(abs(gap) / top_w))
    primary = ranked_up[:2] if gap > 0 else ranked_down[:2]
    if not primary:
        primary = ranked_up[:2] if gap > 0 else ranked_down[:2]
    sign = 1 if gap > 0 else -1
    per = bulk // len(primary)
    rem = bulk % len(primary)
    for i, attr in enumerate(primary):
        pts = per + (1 if i < rem else 0)
        if pts:
            _apply_delta(stats, attr, sign * pts)

    current = calculate_true_ovr(position, stats, [], potential)

    # Greedy fine-tune — prefer top-2 / bottom-2, then any adjustable attr
    # ponytail: O(ΔOVR) worst-case; terminates when no legal ±1 move remains
    guard = 0
    max_steps = (_STAT_MAX - _STAT_MIN) * len(_ATTRS) + 5
    while current != target_ovr and guard < max_steps:
        guard += 1
        need_up = target_ovr > current
        preferred = (ranked_up[:2] if need_up else ranked_down[:2]) or ranked_up
        moved = False
        for attr in preferred:
            if _apply_delta(stats, attr, 1 if need_up else -1):
                moved = True
                break
        if not moved:
            for attr in ranked_up if need_up else ranked_down:
                if _apply_delta(stats, attr, 1 if need_up else -1):
                    moved = True
                    break
        if not moved:
            break
        current = calculate_true_ovr(position, stats, [], potential)

    return current


def create_player_card(
    *,
    position: str,
    rarity: str,
    target_ovr: int,
    first_name: str,
    last_name: str,
    age: int | None = None,
    reference_date: date | None = None,
    rng: random.Random | None = None,
    archetype: ArchetypeDef | None = None,
) -> CreatedPlayerCard:
    """Create a typed player card with archetype identity and target True OVR."""
    r = rng or random
    age_val = age if age is not None else roll_creation_age(r)
    jitter = r.randint(-120, 120)
    dob = dob_from_age(age_val, reference=reference_date, day_jitter=jitter)

    potential = generate_potential(target_ovr, age_val, rarity, position, rng=r)
    arch = archetype or roll_archetype(position, rng=r)
    weights = arch.weights

    stats: dict[str, int] = {}
    for attr, weight in weights.items():
        if weight <= 0:
            # GK sho/dri — keep low but legal
            stats[attr] = _clamp(target_ovr + r.randint(-25, -10))
            continue
        if weight >= 0.25:
            stats[attr] = target_ovr + r.randint(2, 12)
        elif weight >= 0.15:
            stats[attr] = target_ovr + r.randint(-5, 5)
        else:
            stats[attr] = target_ovr + r.randint(-20, -5)
        stats[attr] = _clamp(stats[attr])

    overall = balance_true_ovr(
        position,
        stats,
        target_ovr=target_ovr,
        potential=potential,
        weights=weights,
    )

    return CreatedPlayerCard(
        name=f"{first_name} {last_name}",
        position=position,
        rarity=rarity,
        role=arch.name,
        base_rating=overall,
        overall=overall,
        pac=stats["pac"],
        sho=stats["sho"],
        pas=stats["pas"],
        dri=stats["dri"],
        def_stat=stats["def"],
        phy=stats["phy"],
        potential=potential,
        base_potential=potential,
        age=age_val,
        date_of_birth=dob.isoformat(),
    )

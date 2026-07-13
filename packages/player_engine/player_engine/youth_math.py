# packages/player_engine/player_engine/youth_math.py
"""Academy passive growth math (015) — not apply_card_xp."""
from __future__ import annotations

from dataclasses import dataclass

from .engine import POSITION_WEIGHTS

POINTS_PER_OVR: int = 100
READY_OVR_DEFAULT: int = 65
AGE_OUT_DEFAULT: int = 20

_ATTRS = ("pac", "sho", "pas", "dri", "def", "phy")


@dataclass(frozen=True)
class GrowthResult:
    overall: int
    progress: int
    stats: dict[str, int]
    ovr_gained: int
    is_ready: bool


def academy_daily_points(academy_level: int, potential: int) -> int:
    level = max(1, min(5, int(academy_level)))
    pot = max(0, int(potential))
    return 10 + (5 * level) + (pot // 25)


def star_band(potential: int) -> int:
    pot = int(potential)
    if pot < 75:
        return 1
    if pot < 80:
        return 2
    if pot < 85:
        return 3
    if pot < 90:
        return 4
    return 5


def is_promotion_ready(overall: int, ready_ovr: int = READY_OVR_DEFAULT) -> bool:
    return int(overall) >= int(ready_ovr)


def should_age_out(age: int, age_out: int = AGE_OUT_DEFAULT) -> bool:
    return int(age) >= int(age_out)


def _primary_attrs(position: str) -> list[str]:
    weights = POSITION_WEIGHTS.get(position, POSITION_WEIGHTS["MID"])
    ranked = sorted(
        ((a, w) for a, w in weights.items() if w > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    return [a for a, _ in ranked] or list(_ATTRS)


def _bump_primary_stat(stats: dict[str, int], position: str, potential: int) -> dict[str, int]:
    """+1 to highest-weight attr under potential; try next if capped."""
    out = dict(stats)
    cap = int(potential)
    for attr in _primary_attrs(position):
        cur = int(out.get(attr, 50))
        if cur < cap and cur < 99:
            out[attr] = cur + 1
            return out
    return out


def apply_academy_tick(
    overall: int,
    potential: int,
    progress: int,
    academy_level: int,
    stats: dict[str, int],
    position: str,
    *,
    ready_ovr: int = READY_OVR_DEFAULT,
) -> GrowthResult:
    pot = max(int(overall), int(potential))
    ovr = min(int(overall), pot)
    prog = max(0, int(progress))
    st = {a: int(stats.get(a, 50)) for a in _ATTRS}

    prog += academy_daily_points(academy_level, pot)
    gained = 0
    while prog >= POINTS_PER_OVR and ovr < pot:
        ovr += 1
        prog -= POINTS_PER_OVR
        gained += 1
        st = _bump_primary_stat(st, position, pot)

    return GrowthResult(
        overall=ovr,
        progress=prog,
        stats=st,
        ovr_gained=gained,
        is_ready=is_promotion_ready(ovr, ready_ovr),
    )

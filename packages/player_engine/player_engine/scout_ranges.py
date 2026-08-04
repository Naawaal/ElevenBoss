# packages/player_engine/player_engine/scout_ranges.py
"""Academy visible potential ranges (051) — fog true POT until assessed."""

from __future__ import annotations

from .potential import rarity_potential_cap

# Initial visible span width by YA level (inclusive). Higher YA → tighter first look.
INITIAL_RANGE_WIDTH: dict[int, int] = {1: 12, 2: 10, 3: 8, 4: 6, 5: 5}

# Points trimmed from each side of the interval per assessment tier.
SCOUT_NARROW_EACH_SIDE: dict[str, int] = {
    "quick": 2,
    "standard": 3,
    "deep": 4,
}

DEEP_MIN_RANGE: int = 2
ASSESSMENT_ORDER: tuple[str, ...] = ("none", "quick", "standard", "deep")


def _clamp_level(academy_level: int) -> int:
    return max(1, min(5, int(academy_level)))


def initial_range_width(academy_level: int) -> int:
    return INITIAL_RANGE_WIDTH[_clamp_level(academy_level)]


def init_visible_range(
    potential: int,
    rarity: str,
    academy_level: int,
    *,
    width: int | None = None,
) -> tuple[int, int]:
    """Return (lo, hi) containing true POT, clamped to rarity ceiling."""
    pot = int(potential)
    cap = rarity_potential_cap(rarity)
    pot = max(1, min(pot, cap))
    w = int(width) if width is not None else initial_range_width(academy_level)
    w = max(1, w)
    half = w // 2
    lo = pot - half
    hi = pot + (w - 1 - half)
    lo = max(1, lo)
    hi = min(cap, hi)
    # Ensure containment after clamp
    lo = min(lo, pot)
    hi = max(hi, pot)
    # Prefer restoring width toward the open side when clamped
    span = hi - lo + 1
    if span < w:
        need = w - span
        room_lo = lo - 1
        room_hi = cap - hi
        take_lo = min(room_lo, need // 2 + need % 2)
        lo -= take_lo
        need -= take_lo
        take_hi = min(room_hi, need)
        hi += take_hi
    return int(lo), int(hi)


def narrow_range(
    lo: int,
    hi: int,
    potential: int,
    tier: str,
    *,
    rarity: str,
    min_width: int = DEEP_MIN_RANGE,
) -> tuple[int, int]:
    """Tighten visible bounds toward true POT. Never widens; always contains POT.

    Floor width defaults to DEEP_MIN_RANGE so successive Quick→Deep never
    collapses to an exact POT reveal (FR-010).
    """
    pot = int(potential)
    cap = rarity_potential_cap(rarity)
    cur_lo = max(1, min(int(lo), pot, cap))
    cur_hi = min(cap, max(int(hi), pot))
    if cur_lo > cur_hi:
        cur_lo, cur_hi = pot, pot

    trim = SCOUT_NARROW_EACH_SIDE.get(str(tier).lower())
    if trim is None:
        raise ValueError(f"Unknown scout tier: {tier!r}")

    new_lo = min(pot, cur_lo + trim)
    new_hi = max(pot, cur_hi - trim)
    # Monotonic: never widen beyond prior bounds
    new_lo = max(cur_lo, new_lo)
    new_hi = min(cur_hi, new_hi)
    new_lo = min(new_lo, pot)
    new_hi = max(new_hi, pot)

    floor_w = max(1, int(min_width))
    # Expand within prior bounds to preserve fog floor (including after Quick/Standard)
    while (new_hi - new_lo + 1) < floor_w and (new_lo > cur_lo or new_hi < cur_hi):
        expanded = False
        if new_lo > cur_lo and (new_hi - new_lo + 1) < floor_w:
            new_lo -= 1
            expanded = True
        if new_hi < cur_hi and (new_hi - new_lo + 1) < floor_w:
            new_hi += 1
            expanded = True
        if not expanded:
            break

    new_lo = min(new_lo, pot)
    new_hi = max(new_hi, pot)
    assert new_lo <= pot <= new_hi
    assert new_lo >= cur_lo and new_hi <= cur_hi
    return int(new_lo), int(new_hi)


def star_band_from_interval(lo: int, hi: int) -> int:
    """Stars from midpoint of known interval (not hidden exact POT)."""
    mid = (int(lo) + int(hi)) // 2
    if mid < 75:
        return 1
    if mid < 80:
        return 2
    if mid < 85:
        return 3
    if mid < 90:
        return 4
    return 5


def next_assessment_level(current: str | None, tier: str) -> str:
    """Bump assessment level to the higher of current and completed tier."""
    cur = (current or "none").lower()
    t = str(tier).lower()
    try:
        return ASSESSMENT_ORDER[
            max(ASSESSMENT_ORDER.index(cur), ASSESSMENT_ORDER.index(t))
        ]
    except ValueError:
        return t if t in ASSESSMENT_ORDER else cur

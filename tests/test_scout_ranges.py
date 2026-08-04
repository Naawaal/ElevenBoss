# tests/test_scout_ranges.py
"""Academy scout visible-range math (051)."""

from __future__ import annotations

import pytest

from player_engine.scout_ranges import (
    init_visible_range,
    narrow_range,
    star_band_from_interval,
)


def test_init_contains_potential() -> None:
    for level in range(1, 6):
        for pot in (60, 72, 80, 90):
            rarity = (
                "Common"
                if pot <= 75
                else "Rare"
                if pot <= 85
                else "Epic"
                if pot <= 92
                else "Legendary"
            )
            if rarity == "Common" and pot > 75:
                continue
            lo, hi = init_visible_range(
                min(pot, 75) if rarity == "Common" else pot, rarity, level
            )
            assert lo <= (min(pot, 75) if rarity == "Common" else pot) <= hi


def test_narrow_monotonic_contains() -> None:
    pot = 78
    lo, hi = init_visible_range(pot, "Rare", 2)
    for tier in ("quick", "standard", "deep"):
        nlo, nhi = narrow_range(lo, hi, pot, tier, rarity="Rare")
        assert nlo >= lo and nhi <= hi
        assert nlo <= pot <= nhi
        lo, hi = nlo, nhi
    assert (hi - lo + 1) >= 2


def test_deep_alone_respects_min_width() -> None:
    pot = 78
    lo, hi = init_visible_range(pot, "Rare", 1)  # wide first look
    nlo, nhi = narrow_range(lo, hi, pot, "deep", rarity="Rare")
    assert nlo <= pot <= nhi
    assert (nhi - nlo + 1) >= 2
    assert nlo >= lo and nhi <= hi


def test_narrow_never_widens() -> None:
    lo, hi = 70, 85
    pot = 80
    nlo, nhi = narrow_range(lo, hi, pot, "quick", rarity="Rare")
    assert nlo >= lo and nhi <= hi


def test_star_band_from_interval_uses_midpoint() -> None:
    assert star_band_from_interval(70, 74) == 1
    assert star_band_from_interval(80, 84) == 3


def test_unknown_tier_raises() -> None:
    with pytest.raises(ValueError):
        narrow_range(70, 80, 75, "ultra", rarity="Rare")

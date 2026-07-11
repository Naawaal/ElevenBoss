from __future__ import annotations

import random
from collections import Counter

from player_engine import generate_regen_from_retired, regen_rarity_for_ovr


def test_generate_regen_from_retired() -> None:
    retired = {
        "id": "00000000-0000-0000-0000-000000000001",
        "position": "FWD",
        "overall": 82,
        "potential": 88,
        "base_potential": 88,
    }
    regen = generate_regen_from_retired(
        retired,
        first_names=["Alex"],
        last_names=["Smith"],
        rng=random.Random(0),
    )
    assert regen.position == "FWD"
    assert 55 <= regen.overall <= 70
    assert 16 <= regen.age <= 19
    assert regen.potential >= regen.overall
    assert regen.source_card_id == retired["id"]
    assert regen.role  # archetype from catalog
    assert regen.role != ""
    assert regen.rarity in ("Common", "Rare")


def test_regen_rarity_legend_never_common() -> None:
    counts: Counter[str] = Counter()
    for i in range(400):
        counts[regen_rarity_for_ovr(88, random.Random(i))] += 1
    assert counts["Common"] == 0
    assert abs(counts["Epic"] / 400 - 0.50) <= 0.05
    assert abs(counts["Rare"] / 400 - 0.50) <= 0.05


def test_regen_rarity_band_80_84() -> None:
    counts: Counter[str] = Counter()
    for i in range(400):
        counts[regen_rarity_for_ovr(82, random.Random(i))] += 1
    assert counts["Epic"] == 0
    assert abs(counts["Rare"] / 400 - 0.60) <= 0.05
    assert abs(counts["Common"] / 400 - 0.40) <= 0.05


def test_regen_rarity_band_75_79() -> None:
    counts: Counter[str] = Counter()
    for i in range(400):
        counts[regen_rarity_for_ovr(77, random.Random(i))] += 1
    assert counts["Epic"] == 0
    assert abs(counts["Rare"] / 400 - 0.20) <= 0.05
    assert abs(counts["Common"] / 400 - 0.80) <= 0.05

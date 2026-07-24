"""PackConfig registry and Epic-capped Standard rarity mix (024)."""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import replace
from unittest import mock

import pytest

from gacha import (
    UnknownPackConfigError,
    generate_pack,
    get_pack_config,
    resolve_pack_config,
    sanitize_pack_config,
)
from gacha.pack_configs import PACKS


def test_standard_pack_config() -> None:
    cfg = get_pack_config("standard")
    assert cfg.rarities == ("Common", "Rare", "Epic")
    assert cfg.rarity_weights == (60, 35, 5)
    assert "Legendary" not in cfg.rarities
    assert cfg.position_weights == (10, 30, 30, 30)
    assert cfg.card_count == 5


def test_unknown_pack_raises() -> None:
    with pytest.raises(UnknownPackConfigError):
        get_pack_config("not-a-real-pack")


def test_sanitize_strips_legendary() -> None:
    dirty = replace(
        PACKS["standard"],
        rarities=("Common", "Rare", "Epic", "Legendary"),
        rarity_weights=(60, 30, 8, 2),
    )
    clean = sanitize_pack_config(dirty)
    assert "Legendary" not in clean.rarities
    assert clean.rarities == ("Common", "Rare", "Epic")
    assert clean.rarity_weights == (60, 30, 8)


def test_resolve_invalid_falls_back_to_epic_cap() -> None:
    cfg = resolve_pack_config(
        "standard",
        rarities=("Legendary",),
        rarity_weights=(100,),
    )
    assert cfg.rarities == ("Common", "Rare", "Epic")
    assert cfg.rarity_weights == (60, 35, 5)


def test_resolve_overlay_then_sanitize() -> None:
    cfg = resolve_pack_config(
        "standard",
        rarities=["Common", "Rare", "Epic", "Legendary"],
        rarity_weights=[50, 30, 15, 5],
    )
    assert "Legendary" not in cfg.rarities
    assert cfg.rarity_weights == (50, 30, 15)


def test_standard_rarity_sampling_no_legendary() -> None:
    """SC-001/SC-002: N≥10_000 draws; zero Legendary; Epic within ±2 pp of 5%."""
    cfg = PACKS["standard"]
    r = random.Random(123)
    n = 10_000
    counts: Counter[str] = Counter()
    with mock.patch("gacha.generator.random") as mock_rand:
        mock_rand.choices = r.choices
        mock_rand.randint = r.randint
        mock_rand.choice = r.choice
        mock_rand.random = r.random
        for _ in range(n):
            pack = generate_pack(n=1, pack_id="standard")
            counts[pack.players[0].rarity] += 1

    assert counts.get("Legendary", 0) == 0
    targets = dict(zip(cfg.rarities, cfg.rarity_weights, strict=True))
    for rarity, weight in targets.items():
        pct = 100.0 * counts[rarity] / n
        assert abs(pct - weight) <= 2.0, f"{rarity}: {pct:.2f}% vs {weight}%"


def test_generate_pack_default_size() -> None:
    pack = generate_pack(pack_id="standard")
    assert len(pack.players) == 5
    assert all(p.role for p in pack.players)
    assert all(p.rarity != "Legendary" for p in pack.players)

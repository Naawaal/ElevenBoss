"""PackConfig registry and Standard rarity mix."""
from __future__ import annotations

import random
from collections import Counter
from unittest import mock

import pytest

from gacha import UnknownPackConfigError, generate_pack, get_pack_config
from gacha.pack_configs import PACKS


def test_standard_pack_config() -> None:
    cfg = get_pack_config("standard")
    assert cfg.rarity_weights == (60, 30, 8, 2)
    assert cfg.position_weights == (10, 30, 30, 30)
    assert cfg.card_count == 5


def test_unknown_pack_raises() -> None:
    with pytest.raises(UnknownPackConfigError):
        get_pack_config("not-a-real-pack")


def test_standard_rarity_sampling_tolerance() -> None:
    """SC-004: N≥2000 single-card draws; each rarity within ±3 pp of target."""
    cfg = PACKS["standard"]
    r = random.Random(123)
    n = 2000
    counts: Counter[str] = Counter()
    with mock.patch("gacha.generator.random") as mock_rand:
        mock_rand.choices = r.choices
        mock_rand.randint = r.randint
        mock_rand.choice = r.choice
        mock_rand.random = r.random
        # generate_pack uses module-level random; patch create path via many packs
        for _ in range(n):
            pack = generate_pack(n=1, pack_id="standard")
            counts[pack.players[0].rarity] += 1

    targets = dict(zip(cfg.rarities, cfg.rarity_weights, strict=True))
    for rarity, weight in targets.items():
        pct = 100.0 * counts[rarity] / n
        assert abs(pct - weight) <= 3.0, f"{rarity}: {pct:.2f}% vs {weight}%"


def test_generate_pack_default_size() -> None:
    pack = generate_pack(pack_id="standard")
    assert len(pack.players) == 5
    assert all(p.role for p in pack.players)

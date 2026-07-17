# packages/gacha/gacha/pack_configs.py
"""Named pack product rules (rarity / position mixes)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace


class UnknownPackConfigError(ValueError):
    """Raised when generate_pack / get_pack_config receives an unknown pack id."""


@dataclass(frozen=True)
class PackConfig:
    id: str
    card_count: int
    rarities: tuple[str, ...]
    rarity_weights: tuple[int, ...]
    positions: tuple[str, ...]
    position_weights: tuple[int, ...]


# Epic-capped standard mix (Legendary folded into Epic: former 60/30/8/2 → 60/30/10).
_STANDARD_EPIC_CAP = PackConfig(
    id="standard",
    card_count=5,
    rarities=("Common", "Rare", "Epic"),
    rarity_weights=(60, 30, 10),
    positions=("GK", "DEF", "MID", "FWD"),
    position_weights=(10, 30, 30, 30),
)

PACKS: dict[str, PackConfig] = {
    "standard": _STANDARD_EPIC_CAP,
}


def get_pack_config(pack_id: str) -> PackConfig:
    cfg = PACKS.get(pack_id)
    if cfg is None:
        raise UnknownPackConfigError(f"Unknown pack config id: {pack_id!r}")
    return cfg


def sanitize_pack_config(cfg: PackConfig) -> PackConfig:
    """Drop Legendary from pack mixes; fall back to Epic-capped standard defaults."""
    pairs = [
        (rarity, int(weight))
        for rarity, weight in zip(cfg.rarities, cfg.rarity_weights, strict=False)
        if rarity != "Legendary" and int(weight) > 0
    ]
    if not pairs or len(cfg.rarities) != len(cfg.rarity_weights):
        return _STANDARD_EPIC_CAP if cfg.id == "standard" else replace(
            _STANDARD_EPIC_CAP,
            id=cfg.id,
            card_count=cfg.card_count,
            positions=cfg.positions,
            position_weights=cfg.position_weights,
        )
    rarities = tuple(r for r, _ in pairs)
    weights = tuple(w for _, w in pairs)
    if sum(weights) <= 0 or "Legendary" in rarities:
        return _STANDARD_EPIC_CAP
    return replace(cfg, rarities=rarities, rarity_weights=weights)


def resolve_pack_config(
    pack_id: str,
    *,
    rarities: Sequence[str] | None = None,
    rarity_weights: Sequence[int] | None = None,
) -> PackConfig:
    """Merge optional rarity overrides onto a named pack, then sanitize."""
    base = get_pack_config(pack_id)
    if rarities is not None and rarity_weights is not None:
        r_list = tuple(str(r) for r in rarities)
        w_list = tuple(int(w) for w in rarity_weights)
        if len(r_list) == len(w_list) and len(r_list) > 0:
            base = replace(base, rarities=r_list, rarity_weights=w_list)
    return sanitize_pack_config(base)

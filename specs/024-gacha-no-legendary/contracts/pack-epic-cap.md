# Contract: Pack Epic Cap (pure gacha)

**Feature**: `024-gacha-no-legendary`  
**Module**: `packages/gacha/gacha/pack_configs.py` (+ `generator.py`)

## Defaults

```text
standard.rarities = ("Common", "Rare", "Epic")
standard.rarity_weights = (60, 35, 5)  # 085: Epic 5%; Rare 35%
```

## `sanitize_pack_config(cfg) -> PackConfig`

1. Zip rarities with weights; drop any pair where rarity == `"Legendary"` (case-sensitive match to existing enum).
2. If remaining list empty, or weight sum ≤ 0, or lengths mismatch input → return package standard Epic-capped defaults.
3. Return new `PackConfig` with sanitized tuples (other fields preserved).

## `resolve_pack_config(pack_id, *, rarities=None, weights=None) -> PackConfig`

1. Start from `get_pack_config(pack_id)` (or defaults for `"standard"`).
2. If `rarities` and `weights` both provided and same length, overlay them.
3. Return `sanitize_pack_config(...)`.

## `generate_pack(...)`

Must resolve/sanitize before `random.choices`. Optional kwargs:

```text
rarities: Sequence[str] | None
rarity_weights: Sequence[int] | None
```

When provided (from bot config), pass through `resolve_pack_config`.

## Must not

- Include Legendary in choices for pack pulls
- Call DB
- Alter `generate_support_legendary`

## Tests

- Default config has no Legendary
- Override that includes Legendary is stripped
- Invalid override → defaults
- N≥10_000 single-card rolls → Legendary count 0; Epic within ±2 pp of 10%

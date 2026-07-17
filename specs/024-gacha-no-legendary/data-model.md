# Data Model: Gacha Pack Epic Cap

**Feature**: `024-gacha-no-legendary`

## Entities

### PackConfig (package, existing)

| Field | After this feature (standard) |
|-------|-------------------------------|
| `rarities` | `("Common", "Rare", "Epic")` — no Legendary |
| `rarity_weights` | `(60, 30, 10)` |
| `card_count` | 5 (unchanged) |
| positions / weights | unchanged |

### game_config keys (new)

| Key | Type | Default |
|-----|------|---------|
| `pack_standard_rarities` | JSON string array | `["Common","Rare","Epic"]` |
| `pack_standard_rarity_weights` | JSON number array | `[60,30,10]` |

No new tables. No ALTER on `player_cards`.

### Owned player cards

| Field | Change |
|-------|--------|
| `rarity` including `Legendary` | **Unchanged** — existing rows stay |

### Special grant (out of pack model)

`support_legendary_rewards` / `generate_support_legendary` — unchanged; not part of pack rarity mix.

## Validation rules

1. `len(rarities) == len(rarity_weights) >= 1`
2. All weights > 0 after sanitize
3. `"Legendary"` must not appear in the list used for `random.choices` in pack generation
4. Invalid / empty after sanitize → package defaults `(Common,Rare,Epic)` / `(60,30,10)`

## State transitions

None for cards. Pack open: roll rarity ∈ {Common, Rare, Epic} only.

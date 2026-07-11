# Contract: Pack Configuration

## Purpose

Named pack product rules live outside generation control flow so rarity/position mixes can change (or new pack ids can be added) without editing archetype or OVR-balancing logic.

## API

```text
get_pack_config(pack_id: str) -> PackConfig
generate_pack(n: int | None = None, *, pack_id: str = "standard") -> GachaPack
```

Package: `packages/gacha`.

## PackConfig fields

| Field | Meaning |
|-------|---------|
| `id` | Stable key (`standard`) |
| `card_count` | Default cards per pack |
| `rarities` | Ordered rarity labels |
| `rarity_weights` | Parallel weights (Standard: 60, 30, 8, 2) |
| `positions` | `GK, DEF, MID, FWD` |
| `position_weights` | Parallel weights (Standard: 10, 30, 30, 30) |

## Standard pack (v1 live)

| Rule | Value |
|------|-------|
| id | `standard` |
| card_count | 5 |
| rarity mix | Common 60% / Rare 30% / Epic 8% / Legendary 2% |
| position mix | GK 10% / DEF 30% / MID 30% / FWD 30% |

`/store` daily claim continues to call `generate_pack` with this default — **no economy or cooldown change**.

## Errors

- Unknown `pack_id` → raise typed error before rolling cards (no silent fallback weights).

## Extensibility (v1 readiness, not live SKU)

A future Defender Pack would be a new `PackConfig` entry (e.g. heavier DEF weights) plus a call-site selector. **Do not** add a `/store` button or claim path for it in this feature.

## Non-goals

- DB-backed `game_config` pack tables
- Changing published Standard mix
- Starter-squad / youth intake blueprints (remain their own position lists)

# Data Model: Gacha Card Archetypes & Factory Reliability

**Feature**: `005-gacha-archetypes` | **Date**: 2026-07-11

## Persisted entities

### Player card (`player_cards`) — existing

| Field | Change |
|-------|--------|
| `role TEXT DEFAULT 'Balanced'` | **Now populated** at insert with archetype display name (e.g. `Poacher`). No new column. |
| `pac/sho/pas/dri/def/phy`, `overall`, `potential`, … | Unchanged schema; values shaped by archetype + deterministic balance |
| Historical rows | Unchanged (`Balanced` or prior values) |

### Scouting pool row (`scouting_pool_players`)

| Field | Change |
|-------|--------|
| `role TEXT NOT NULL DEFAULT 'Balanced'` | **New column** (migration 051) so regen → pool → purchase copies identity |

### Intake RPC payloads (`jsonb` card objects)

Shared logical fields (register, daily pack, youth):

| Key | Type | Required |
|-----|------|----------|
| `name`, `position`, `rarity` | text | yes |
| `base_rating`, `overall` | int | yes |
| `pac`…`phy`, `def` | int | yes (defaults 50 if omitted) |
| `potential`, `base_potential` | int | yes (youth/register enforce) |
| `age`, `date_of_birth` | int / date | dob preferred |
| `role` | text | **new** — COALESCE to `Balanced` in SQL |

## In-memory / package entities

### ArchetypeDef

| Field | Meaning |
|-------|---------|
| `name` | Display + `role` value |
| `position` | `GK` \| `DEF` \| `MID` \| `FWD` |
| `weights` | Map of six attrs → float (creation distribution) |
| `roll_weight` | Relative chance among siblings |

### CreatedPlayerCard (factory output)

Validated creation contract. See [contracts/created-player-card.md](./contracts/created-player-card.md).

| Field | Notes |
|-------|-------|
| `name`, `position`, `rarity` | identity |
| `overall`, `base_rating` | equal after balance; = True OVR |
| `pac`…`phy` | clamped |
| `potential`, `base_potential` | from potential pipe |
| `age`, `date_of_birth` | DOB ISO string or date |
| `role` | archetype name |

### PackConfig

See [contracts/pack-config.md](./contracts/pack-config.md).

| Field | Notes |
|-------|-------|
| `id` | e.g. `standard` |
| `card_count` | default 5 |
| `rarities` + `rarity_weights` | Standard 60/30/8/2 |
| `positions` + `position_weights` | 10/30/30/30 |

### GachaPlayer

Existing pack UX model + `role: str`.

## Creation pipeline (state)

```text
position + rarity + target_ovr + names
        │
        ▼
  roll_archetype(position)
        │
        ▼
  provisional stats (jitter by weight bands)
        │
        ▼
  deterministic True OVR balance → overall == target (if bounds allow)
        │
        ▼
  CreatedPlayerCard (role = archetype.name)
        │
        ├──► GachaPlayer / pack reveal
        └──► card_rpc_payload (+ role) → RPC INSERT
```

## Validation rules

- Attribute bounds: 10–99 (factory clamp; match current factory).
- `overall == calculate_true_ovr(position, stats, [], potential)` after balance when achievable.
- `role` non-empty; must be a catalog name for that position for newly generated cards.
- Pack `rarity_weights` length equals `rarities`; same for positions.
- Unknown `pack_id` → error before any card roll.

## Relationships

```text
PackConfig ──generates──► GachaPlayer ──payload──► player_cards.role
ArchetypeDef ──shapes──► CreatedPlayerCard.role / stats
CreatedPlayerCard ──regen──► scouting_pool_players.role ──purchase──► player_cards.role
```

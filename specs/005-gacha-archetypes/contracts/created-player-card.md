# Contract: Created Player Card

## Purpose

Typed boundary for all procedural card creation (`create_player_card` and callers). Ensures archetype `role`, six attrs, and True OVR are present before Discord or Supabase serialization.

## API

```text
create_player_card(
  *,
  position: str,
  rarity: str,
  target_ovr: int,
  first_name: str,
  last_name: str,
  age: int | None = None,
  reference_date: date | None = None,
  rng: random.Random | None = None,
) -> CreatedPlayerCard
```

Package: `packages/player_engine` (pure; no Discord/DB).

## Required fields (`CreatedPlayerCard`)

| Field | Constraint |
|-------|------------|
| `name` | `"{first} {last}"` |
| `position` | `GK\|DEF\|MID\|FWD` |
| `rarity` | `Common\|Rare\|Epic\|Legendary` |
| `role` | Non-empty archetype display name for `position` |
| `overall`, `base_rating` | Equal; match True OVR after balance when bounds allow |
| `pac, sho, pas, dri, def, phy` | Integers in [10, 99] (`def` may use alias for JSON) |
| `potential`, `base_potential` | Valid potential pipe outputs |
| `age` | Creation age |
| `date_of_birth` | ISO date string (or date serialized at dump) |

## Behavioral guarantees

1. Archetype selected **before** attribute jitter.
2. Attribute shape follows archetype creation weights (not a single static position table alone).
3. No capped “abandon after N attempts” balancing; prefer exact `target_ovr`.
4. `playstyles=[]` at creation for True OVR (unchanged today).

## Consumers

| Consumer | Obligation |
|----------|------------|
| `gacha.generator` | Map to `GachaPlayer` including `role` |
| `youth_intake` / `regen_pool` | Preserve `role` through any POT overrides |
| `card_rpc_payload` | Include `"role": player.role` |

## Non-goals

- Changing `calculate_true_ovr` / PlayStyle synergy
- Backfilling historical cards

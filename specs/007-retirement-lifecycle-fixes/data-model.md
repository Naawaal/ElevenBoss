# Data Model: Retirement Lifecycle Fixes

**Feature**: `007-retirement-lifecycle-fixes` | **Date**: 2026-07-11

## Persisted entities (changed)

### `players` (extend)

| Column | Type | Rules |
|--------|------|-------|
| `squad_invalid` | `BOOLEAN NOT NULL DEFAULT FALSE` | Set when retirement leaves an unfilled starting slot; cleared when a valid full starting XI is saved or auto-promote restores 11 |

No new tables.

### `player_cards` (existing — decline / retire)

| Field | Role |
|-------|------|
| `date_of_birth`, `age` | Unchanged lifecycle source |
| `pac`, `sho`, `pas`, `dri`, `def`, `phy`, `overall` | Decline mutates attrs + OVR recalc |
| `is_retired`, `retired_at`, `retirement_notified_at` | Unchanged semantics |
| `position` | Used for auto-promote match vs slot role |

### `squad_assignments` (existing)

| Field | Role |
|-------|------|
| `(discord_id, position_slot)` | Starting XI; vacated on retire then optionally refilled |
| `player_card_id` | Removed on retire; may be replaced by reserve |

### `squads` (existing)

| Field | Role |
|-------|------|
| `formation` | Input to `formation_slot_role` for auto-promote |

### `scouting_pool_players` (existing)

Unchanged schema; rarity of inserted regen cards changes via generator only.

## Derived / ephemeral

| Concept | Definition |
|---------|------------|
| Reserve (bench cover) | Owned, non-retired card whose id is **not** in the club’s `squad_assignments` |
| Slot role | `formation_slot_role(formation, position_slot)` ∈ {GK, DEF, MID, FWD} |
| Peak OVR for rarity | Retired card’s `overall` at regen generation time |

## State transitions

### Card age year advance

```text
[Active, age = N]
  → season aging detects DOB age M > N
  → for each year A in (N+1)..M:
       apply yearly_stat_decline(A) with floors
       recalculate OVR
  → if age >= retirement_age → retire_player_card
```

### Retirement vacancy

```text
[Starter assigned to slot S]
  → retire_player_card
  → DELETE assignment for card
  → mark card retired
  → if eligible reserve exists for slot S:
       INSERT reserve into S
       if club now has 11 starters → squad_invalid = FALSE (or leave false)
  → else:
       squad_invalid = TRUE
```

### Repair

```text
[squad_invalid = TRUE]
  → manager set_formation_and_assignments with 11 valid cards
  → squad_invalid = FALSE
  → match starts allowed
```

### Regen rarity (no persisted state change beyond listing)

```text
Retired card overall ≥ 75
  → generate_regen_from_retired
  → rarity = weighted(overall) per FR-014
  → insert scouting listing (existing RPC)
```

## Validation rules

- Attribute floors: each of pac/sho/pas/dri/def/phy ≥ 1 after decline.
- Auto-promote candidate must match slot role exactly (no cross-position).
- `squad_invalid` may be TRUE only when starting XI count &lt; 11 **or** after an unresolved starter retirement (implementation should set TRUE only on unresolved vacancy; count check remains authoritative for matches).
- Regen Common rate for overall ≥ 85 must be 0.

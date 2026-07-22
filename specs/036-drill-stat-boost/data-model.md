# Data Model: Drill Attribute Boost

**Feature**: `036-drill-stat-boost` | **Date**: 2026-07-22

## Overview

No new tables or columns. The feature reuses existing card attributes and drill identity, and extends the **outcome shape** of `process_stat_drill`.

## Entities

### Stat Training Drill (catalog identity)

| Field | Source | Notes |
|-------|--------|-------|
| `drill_id` | `pac_sprint`, `sho_finishing`, `pas_distribution`, `dri_dribble`, `def_tackling`, `phy_strength` | Unchanged |
| `target_stat` | `pac` / `sho` / `pas` / `dri` / `def` / `phy` | 1:1 map (package `DRILL_CATALOG` + SQL CASE) |
| `tier` | basic vs advanced (by card level vs config) | Affects cost/XP only — **not** boost size |

### Player Card (mutated fields)

| Field | Role |
|-------|------|
| `pac`…`phy` | Target of optional `+1` |
| `overall` | Recalculated via `recalculate_card_ovr` when boost applies |
| `potential` | Ceiling for projected overall |
| `level`, `xp`, … | Unchanged XP path via `apply_card_xp` |
| `skill_points` | **Not** decremented by drill boost |

### Club / daily counters (unchanged)

| Field | Role |
|-------|------|
| `players.daily_drill_count` / `daily_drill_reset_at` | Club 20/day soft-reset |
| `player_drill_daily_log` | Per-card 5/day |
| `players.coins` / `action_energy` | Via `apply_club_economy` |

### Drill Outcome (logical result)

| Field | Type | Meaning |
|-------|------|---------|
| XP / economy / progression | existing | Unchanged semantics |
| `stat_boosted` | bool | Whether `+1` was written |
| `stat` | text | Uppercase attribute code when known (`SHO`, …) |
| `stat_delta` | int | `1` if boosted else `0` |
| `new_stat_value` | int \| null | Value after boost when boosted |
| `new_ovr` | int | Overall after drill (post-recalc if boosted; else prior overall) |
| `boost_block_reason` | text \| null | Stable reason code when not boosted |

## Validation rules

1. Boost amount is exactly **1** when applied.
2. Never write if current attribute ≥ **99**.
3. Never write if current `overall` ≥ `potential`.
4. Never write if `peek_card_ovr(..., stat+1) > potential`.
5. Boost does not require or consume skill points.
6. Blocked boost does not roll back XP, coins, energy, or daily counters.

## State transitions

```text
[Drill gates pass]
        │
        ▼
  Evaluate boost eligibility (read-only)
        │
        ├─ eligible ──► write +1 attribute ──► recalculate overall
        │
        └─ blocked ──► no attribute write (reason recorded)
        │
        ▼
  Charge economy + increment daily counters (always)
        │
        ▼
  apply_card_xp (always)
        │
        ▼
  Return outcome (XP + boost metadata)
```

*(Charge-before-write order may be swapped with write-before-XP as long as both happen only after gates pass and blocked boost never raises away the XP path — see research R2/R4.)*

## Relationships

- Drill catalog → target attribute (static).
- Outcome → Training Drills UI summary / select preview.
- Skill allocation remains a separate mutation path sharing the same ceilings.

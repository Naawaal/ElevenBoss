# Data Model: Evolution Start Button Fix

**Feature**: `028-evolution-start-button` | **Date**: 2026-07-22

No new tables or columns. This fix realigns existing hub status fields with live `game_config` and start rules.

## Entities (logical)

### Club Evolution Hub Status

Returned by `get_evolution_hub_status` for one club (`p_owner_id`).

| Field | Meaning | Validation / rules |
|-------|---------|-------------------|
| `active_count` | Count of `active_evolutions` with `status = 'active'` | ≥ 0 |
| `max_active` | Slot cap from config (`evolution_max_active`, default 3) | ≥ 1 |
| `slots_label` | Display `"{active}/{max} slots used"` | Derived |
| `last_evolution_started_at` | Club cold-start timestamp | Nullable |
| `cooldown_ends_at` | `last_started + cooldown_hours` | Null if never started |
| `cooldown_remaining_seconds` | Seconds until cold start allowed | 0 when ready |
| `can_cold_start` | Slot free **and** cooldown elapsed (or never started) | Boolean |
| `can_replace` | Cancel after last start grants replacement **and** slot free | Boolean |
| `can_start` | `can_cold_start OR can_replace` | Drives Start button |
| `training_energy` / energy | Energy shown on hub | Prefer action energy if aligned |
| `start_energy_cost` | Energy to start a track | From `evolution_start_energy` |
| `start_coin_flat` | Flat coin component | From `evolution_start_flat` (**additive**) |
| `start_coin_ovr_mult` | Per-OVR coin component | From `evolution_start_ovr_mult` |
| `start_coin_multiplier` | Back-compat alias of ovr mult | Must **not** stay stuck at legacy 10 |
| `active` | Active track list | Includes card name / progress |
| `recent_completed` | Last few completed tracks | Display only |

### Cold-Start Cooldown

| Attribute | Rule |
|-----------|------|
| Trigger | Successful cold start sets `players.last_evolution_started_at = now()` |
| Duration | `game_config.evolution_cooldown_hours` (seeded 6; start RPC default fallback 10) |
| Bypass | Replacement credit: cancel with `cancelled_at > last_evolution_started_at` while slots remain |
| Hub vs start | Must use identical duration source |

### Active Evolution Slot

Unchanged: one row in `active_evolutions` with `status = 'active'` consumes one club slot until completed or cancelled.

### Start Cost (display)

| Component | Config key | Package mirror |
|-----------|------------|----------------|
| Energy | `evolution_start_energy` | `EVOLUTION_START_ENERGY` (25) |
| Coins | `evolution_start_flat` + `evolution_start_ovr_mult × OVR` | `EVOLUTION_START_FLAT` + `EVOLUTION_START_OVR_MULT` |

Legacy hub copy `10×OVR` (no flat) is obsolete and must not appear.

## State transitions (unchanged product rules)

```text
[Idle / cooldown]
    -- cold start (slot free, cooldown ok) --> [Active track]
    -- cancel (fee) --> [Cancelled] + replacement credit until next cold start timestamp advances
[Active track]
    -- matches complete + claim --> [Completed] (slot frees)
```

This feature does **not** change transitions; it only makes hub **eligibility flags and timers** match the start gate that already enforces them.

# Data Model: Recovery Energy, Hub Cleanup & Energy Cap

**Feature**: `010-recovery-energy-cleanup` | **Date**: 2026-07-12

No new tables. Config + constraint + club column updates.

## Entities

### `game_config` (existing)

| Key | Before | After |
|-----|--------|-------|
| `fatigue_recovery_energy` | 10 | **5** |
| `energy_max` | 100 | **120** |

### `players` (existing)

| Field | Change |
|-------|--------|
| `max_energy` | Backfill to ≥120; register default 120 |
| `action_energy` | Default 120; ceiling via `energy_max` |
| `energy`, `training_energy` | CHECK upper bound **100 → 120**; dual-written with action energy |

### Recovery Session (logical)

Cost reads `fatigue_recovery_energy` (5). Unchanged fatigue grant / caps / XP rules.

### Surfaces (UI, not DB)

| Surface | Change |
|---------|--------|
| Store → Club Facilities | YA + TG only |
| `/profile` Manage Hospital | Unchanged entry to `HospitalPanelView` |
| `/club-finances` | Removed |
| `/profile` Finances | Kept |

## Validation

- Action energy always `0 ≤ value ≤ energy_max` (120).
- Legacy column CHECKs must allow 120 or dual-write fails.
- Morale and other `/100` scales unchanged.

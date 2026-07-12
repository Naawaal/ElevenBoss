# Data Model: Active Fatigue Recovery

**Feature**: `009-fatigue-recovery` | **Date**: 2026-07-12

No new tables. Additive config + RPC behavior on existing entities.

## Entities

### Player Card (`player_cards`) — existing

| Field | Role for this feature |
|-------|------------------------|
| `id`, `owner_id` | Ownership / lock target |
| `fatigue` (0–100) | Increased by Recovery Session (+40 default) and daily passive |
| `injury_tier`, `in_hospital` | Block Recovery Session when set / true |
| `is_retired` | Block Recovery |
| XP / level / stats | **Must not change** on Recovery Session |

**Validation (Recovery start)**:
- Owned by caller, not retired
- `fatigue < 100`
- `injury_tier IS NULL` and not `in_hospital`
- Not in `active_evolutions` with `status = 'active'`
- Club not in live match (`assert_not_in_match`)

### Club (`players`) — existing

| Field | Role |
|-------|------|
| `discord_id` | Owner |
| `action_energy` | Debited via `apply_club_economy` (Basic drill energy) |
| `daily_drill_count`, `daily_drill_reset_at` | Shared capacity with skill drills |
| `training_ground_level` (1–5) | Scales daily passive fatigue |

### Drill daily log (`player_drill_daily_log`) — existing

| Field | Role |
|-------|------|
| `card_id`, `drill_date`, `count` | Per-card daily cap (5); Recovery increments like skill drills |

### Game config (`game_config`) — seeds in migration 054

| Key | Default | Meaning |
|-----|---------|---------|
| `fatigue_recovery_session` | 40 | Fatigue granted per successful Recovery Session |
| `fatigue_recovery_energy` | 10 | Action energy cost (mirror Basic drill) |
| `fatigue_passive_base` | 15 | Non-hospital daily base |
| `fatigue_passive_tg_per_level` | 5 | Added per TG level |
| `fatigue_hospital_per_day` | 45 | Unchanged hospital path |
| `fatigue_bench_per_match` | 15 | Unchanged; not written by this feature |

Legacy `fatigue_passive_per_day` (20) is superseded for non-hospital cards by base + TG formula.

## State transitions

### Fatigue (card)

```text
[0–100]
   │
   ├─ competitive start ──► drain (unchanged)
   ├─ competitive bench ──► +15 bench rest (unchanged)
   ├─ Recovery Session ───► +fatigue_recovery_session (cap 100)
   └─ daily tick ─────────► +passive(TG) or +hospital (cap 100)
```

### Recovery Session (logical)

```text
idle → validate → debit energy + drill capacity → bump fatigue → done
         ↘ reject (energy / caps / injury / full / evo / match)
```

No queued / in-progress session state (instant RPC).

## Relationships

- Card `owner_id` → `players.discord_id`
- Passive daily amount depends on owner’s `training_ground_level`
- Recovery Session and skill drills share drill capacity entities; they do not share XP pipe

## Out of model

- No physio inventory / consumable rows
- No recovery job / cooldown table
- No new facility type (TG reused)

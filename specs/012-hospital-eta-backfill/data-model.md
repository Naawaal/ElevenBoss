# Data Model: Hospital ETA Backfill

**Feature**: `012-hospital-eta-backfill`  
**Schema impact**: **No new tables/columns.** Updates existing rows; adds RPC function.

---

## Tables touched

### `hospital_patients` (active: `discharge_date IS NULL`)

| Column | Role |
|--------|------|
| `admission_date` | Anchor for served time / candidate ETA |
| `injury_tier` | Selects base 1 / 4 / 7 |
| `expected_recovery_date` | Shortened via `LEAST(old, admission + new_total)` |
| `discharge_date` | Set on early recovery |
| `owner_id` / `player_card_id` | Join + DM summary |

### `players`

| Column | Role |
|--------|------|
| `hospital_level` | Current facility level for CEIL curve |
| `discord_id` | DM target |

### `player_cards`

| Column | Role |
|--------|------|
| `injury_tier` / `injury_started_at` / `injury_recovery_days` / `in_hospital` | Sync or clear |
| `fatigue` | +25 on early hospital recovery (cap 100) |
| `name` | DM / summary |
| `is_retired` | Skip retired |

---

## Derived values (not stored as new columns)

| Name | Definition |
|------|------------|
| `base_days` | `{1:1, 2:4, 3:7}[tier]` |
| `new_total_days` | `CEIL(base_days / (1 + 0.2 * hospital_level))` |
| `candidate_eta` | `admission_date + new_total_days days` |
| `final_eta` | `LEAST(expected_recovery_date, candidate_eta)` |
| `early_discharge` | `NOW() >= final_eta` |

---

## RPC result shape (conceptual)

```json
{
  "hospital_shortened": 0,
  "hospital_unchanged": 0,
  "hospital_early_discharged": 0,
  "overflow_shortened": 0,
  "overflow_cleared": 0,
  "skipped": 0,
  "early_discharged": [
    {
      "owner_id": 0,
      "player_card_id": "…",
      "name": "…",
      "tier": 3
    }
  ]
}
```

---

## Validation / guards

- Migration requires functions `admit_to_hospital` / `process_daily_recovery` already present (post-050+).
- Prefer documenting prerequisite: migration `056` applied.
- Idempotent: second call → counts mostly `*_unchanged` / empty `early_discharged`.

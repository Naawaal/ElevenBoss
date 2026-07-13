# Contract: `backfill_tier_fatigue_rebalance` RPC

**Feature**: `016-tier-fatigue-rebalance`  
**Migration**: `061_tier_fatigue_rebalance.sql`  
**Pattern**: Same fairness class as `057` `backfill_injury_eta_fairness`

## Signature

```text
backfill_tier_fatigue_rebalance() RETURNS jsonb
```

Idempotent SECURITY DEFINER. Callable from `scratch/apply_migration_061.py` after DDL.

## Behavior

### A. Hospital patients (open / not discharged)

For each row in `hospital_patients` with null `discharge_date`:

1. Resolve club `intensity_tier` and `hospital_level` from `players`.
2. Resolve injury severity from patient/card `injury_tier`.
3. `new_total_days = recovery_days_for_tier_intensity(severity, intensity_tier, hospital_level)`.
4. `candidate_eta = admission_date + new_total_days days`.
5. `final_eta = LEAST(expected_recovery_date, candidate_eta)` (never lengthen).
6. If `now() >= final_eta` → early recovery discharge (same end-state as daily recovery clear: clear injury flags, set discharge, grant +25 fatigue cap 100 — match 057 / daily path).
7. Else UPDATE `expected_recovery_date = final_eta` and sync remaining `injury_recovery_days` if used.

### B. Overflow untreated

Cards with `injury_tier IS NOT NULL AND in_hospital = FALSE`: fair remaining using new untreated bases × severity; clear if remaining 0.

### C. Fatigue floor

```sql
UPDATE player_cards
SET fatigue = GREATEST(fatigue, 50)
WHERE injury_tier IS NULL
  AND COALESCE(in_hospital, FALSE) = FALSE
  AND COALESCE(is_retired, FALSE) = FALSE;  -- if column exists
```

### Return JSON (illustrative)

```json
{
  "hospital_shortened": 12,
  "hospital_early_discharged": 3,
  "overflow_updated": 2,
  "overflow_cleared": 1,
  "fatigue_floored": 400,
  "early_discharged": [{"owner_id": 1, "card_id": "...", "name": "..."}]
}
```

## Notifications

Optional best-effort DMs for early discharges **after** RPC commits (scratch/bot one-shot). Failure must not roll back data.

## Guard

Add `function:backfill_tier_fatigue_rebalance` to `verify_required_schema.sql`.

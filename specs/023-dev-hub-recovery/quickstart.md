# Quickstart: Development Hub Recovery

**Feature**: `023-dev-hub-recovery`

Validate the relocation end-to-end after migration `066` and bot deploy. See [contracts/](./contracts/) and [data-model.md](./data-model.md) for rules.

## Prerequisites

- Migration `066_dev_hub_recovery.sql` applied
- `supabase/scripts/verify_required_schema.sql` passes (`process_recovery_batch` present)
- Bot running with updated `development_cog`
- Test club with action energy ≥ 15 and at least three non-injured roster cards with fatigue &lt; 100
- Optional: one injured / in-hospital card and one at fatigue 100 for negative tests

## 1. Hub Recover — single player

1. `/development` → confirm **Recover** button is visible.
2. Tap Recover → select **one** tired player (fatigue % visible) → Continue.
3. Confirm embed shows +fatigue grant and **5⚡** (or current config) total.
4. Confirm → success message; fatigue up; energy −5; XP unchanged.
5. Hub refreshes.

**Expect**: Never opened Training Drills.

## 2. Batch of three

1. Recover → select **three** eligible players → Continue.
2. Confirm shows **15⚡** total (if energy config is 5).
3. Confirm with sufficient energy → all three gain fatigue; energy −15 once.
4. Repeat with energy &lt; 15 → **no** fatigue changes; affordability error.

## 3. Eligibility filters

1. Injured or in-Hospital card does **not** appear (or cannot confirm).
2. Fatigue 100 card does **not** appear.
3. Empty eligible set → clear empty-state (no silent crash).

## 4. Training Drills are skill-only

1. `/development` → Training Drills.
2. Player + drill selects show **no** Recovery Session option.
3. Embed copy does **not** advertise Recovery Sessions.
4. Run a Basic skill drill → still works (XP/coins/energy/slots).

## 5. Double-tap / race

1. Confirm Recover once; immediately mash Confirm again on a stale view if possible.
2. At most one successful batch charge for that selection.

## 6. Automated checks

```bash
pytest tests/test_fatigue_injury_math.py -q
# plus any new recovery eligibility / batch energy tests added in tasks
```

## Rollback smoke

If rolling back: hub has no Recover; Training Drills again offers Recovery; Hospital/passive daily recovery still behave as before 023.

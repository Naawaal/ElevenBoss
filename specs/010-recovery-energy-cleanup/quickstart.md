# Quickstart: Recovery Energy, Hub Cleanup & Energy Cap

**Feature**: `010-recovery-energy-cleanup` | **Date**: 2026-07-12

Assumes migration `055` applied and bot redeployed (slash sync).

## Automated

```bash
pytest tests/test_fatigue_injury_math.py tests/test_match_loop_hardening.py -q
```

Expect: fatigue math unchanged; energy time-to-full tests still pass with explicit max args (update if defaults asserted).

## 1. Recovery costs 5

1. `/development` → Training Drills → Recovery Session preview shows **5⚡**.
2. Run with ≥5 energy → success; energy −5.
3. Basic skill drill still costs Basic energy (typically 10), not 5.

## 2. Energy max 120

1. Energy status on `/store` or `/development` shows `n/120`.
2. Regen/refill does not exceed 120.
3. SQL: `SELECT max_energy FROM players LIMIT 5` → all ≥ 120 after backfill.

## 3. Store facilities — no Hospital

1. `/store` → Club Facilities: YA + TG only; no Hospital field/buttons.
2. `/profile` → Manage Hospital still opens panel; upgrade/admit still work.

## 4. No `/club-finances`

1. Slash picker: command absent.
2. `/profile` → Finances still shows balance/wages/facilities summary.

## 5. Copy grep

Search bot UI strings for `Club Facilities → Hospital`, `build one in the Store`, `/club-finances` — expect zero player instructions pointing at removed surfaces.

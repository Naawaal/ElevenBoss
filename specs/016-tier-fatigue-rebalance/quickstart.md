# Quickstart: Division-Tier Fatigue & Injury Rebalance

**Feature**: `016-tier-fatigue-rebalance`  
**Purpose**: Validate the feature end-to-end after implementation (not a substitute for `tasks.md`).

## Prerequisites

- Migration `061_tier_fatigue_rebalance.sql` applied
- `supabase/scripts/verify_required_schema.sql` passes (`players.intensity_tier`, `backfill_tier_fatigue_rebalance`)
- Bot running against that DB
- Unit tests: `pytest tests/test_tier_fatigue_rebalance.py` (or extended fatigue/injury math tests) green

## 1. Pure math smoke

```bash
pytest tests/test_tier_fatigue_rebalance.py -q
```

Expect anchors from [fatigue-drain-recovery-math.md](./contracts/fatigue-drain-recovery-math.md) and [injury-hospital-math.md](./contracts/injury-hospital-math.md): Tier1 Neutral PHY70 drain **1**; Tier1 TG3 passive **41**; Tier3 Moderate H5 days **4**.

## 2. Intensity column + Monday write

1. Confirm `players.intensity_tier` matches map for sample Grassroots (1) and Legendary (3) clubs after migration backfill.
2. After a Monday reset (or dry-run of the job’s division UPDATE path), confirm promo Amateur→Semi-Pro sets tier **1→2**.

## 3. Manager UX

| Check | Steps | Expect |
|-------|-------|--------|
| Hospital T1 | Grassroots club → `/store` Facilities → Hospital | Low intensity copy; no “High / longer” warning |
| Hospital T3 | Elite/Legendary → Hospital | High intensity + longer-base copy |
| Profile injury | Injured card on profile | ETA + base/facility breakdown |
| Pre-match | Set ≥1 starter fatigue &lt; 30 → open competitive battle ticket | Warning with correct count; match still startable |
| Pre-match clean | All starters ≥ 30 | No warning |

## 4. Match fitness

1. Tier 1 Neutral match: starter drains near new low curve (not old base-18).
2. Confirm rating-gap opponents no longer add a flat +5 intensity surcharge.
3. Bot match: human fatigue updates; injury rolls use human tier bases.

## 5. Backfill

```text
RPC backfill_tier_fatigue_rebalance()
```

1. Seed (or use) an open hospital stay with a far ETA; after RPC, ETA ≤ prior; early discharge if served past new total.
2. Uninjured card at fatigue 10 → fatigue ≥ 50.
3. Re-run RPC → idempotent (no further unjustified changes).

## 6. Changelog

`change_log.md` mentions tiered intensity, UI transparency, and migration fairness.

## Out of scope checks (must NOT appear)

- Emergency grey / academy soft-lock filler
- New `/hospital` or `/intensity` slash command
- Cup-specific fatigue downgrade path

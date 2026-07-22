# Quickstart: Drill Attribute Boost

**Feature**: `036-drill-stat-boost` | **Validate after implement**

## Prerequisites

- Migration `078_drill_stat_boost.sql` applied to the target DB
- `supabase/scripts/verify_required_schema.sql` passes (`process_stat_drill` still present)
- Bot running with updated `development_cog` + `drill_rpc` parser
- Test club with:
  - **A)** Uncapped card (room under 99 and potential) for Finishing Drill
  - **B)** Card with target attr at 99 **or** at/near potential so `+1` would exceed pot

Contracts: [process-stat-drill-boost.md](./contracts/process-stat-drill-boost.md), [drill-hub-stat-copy.md](./contracts/drill-hub-stat-copy.md).

## Automated checks

```bash
pytest tests/test_drill_stat_boost.py tests/test_progression_caps.py -q
```

Expect: parser defaults + boost/block field shaping; existing pot/99 gates still green.

Optional: `python scratch/smoke_drill_stat_boost_078.py` if present (scripted RPC on A/B cards).

## Manual hub path

1. `/development` → **Training Drills**.
2. Confirm menu text mentions XP **and** attribute attempt (not “XP only”).
3. Select card **A** → Finishing Drill option shows `+1 SHO` (or equivalent) with XP/energy.
4. **Run Drill** → summary shows XP **and** `+1 SHO`; OVR updates if the formula moved; no “OVR unchanged” claim if OVR changed.
5. Select card **B** → option does not promise a guaranteed `+1` (capped hint).
6. **Run Drill** → XP still granted; attribute unchanged; summary states block reason; energy/coins/daily counters consumed.
7. Confirm Allocate Skills still works and was not charged by the drill.

## Regression spot-checks

- Club 20 / card 5 limits still reject with existing errors.
- Injured / hospital / evolution / transfer-listed / match-locked cards still blocked.
- Double-tap Run Drill does not double-apply boost (single successful completion).

## Done when

- [ ] SC-001 / SC-002 class cases pass on A/B
- [ ] Summary honesty matches [drill-hub-stat-copy.md](./contracts/drill-hub-stat-copy.md)
- [ ] AGENTS + v1.0.0 “XP only” drill wording updated
- [ ] `change_log.md` notes the player-facing change

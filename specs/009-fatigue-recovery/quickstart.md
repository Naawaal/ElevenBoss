# Quickstart: Active Fatigue Recovery

**Feature**: `009-fatigue-recovery` | **Date**: 2026-07-12

Manual validation after implementation. Assumes migration `054` applied and `verify_required_schema.sql` passes.

## Prerequisites

- DB: `process_recovery_session` present; `process_daily_recovery` uses TG-scaled passive
- `game_config` keys: `fatigue_recovery_session`, `fatigue_recovery_energy`, `fatigue_passive_base`, `fatigue_passive_tg_per_level`
- Bot deployed with Development Training Drills Recovery UI
- Test club with:
  - At least one non-injured card with `fatigue` well below 100 (e.g. ≤ 60)
  - Action energy ≥ Basic drill cost (default 10)
  - Remaining club/card daily drill capacity
  - Known `training_ground_level` (try L1 and L5 if possible)

## Automated checks

```bash
pytest tests/test_fatigue_injury_math.py -q
```

Expect: TG1 passive amount 20; TG5 amount 40; hospital path ignores TG; recovery session clamps at 100; bench rest still +15.

## 1. Happy path — Recovery Session

1. `/development` → **Training Drills** → select fatigued eligible player.
2. Choose **Recovery Session** (not a skill drill).
3. Confirm: copy shows +fatigue, 0 XP, energy cost, 0 coins.
4. Confirm action.
5. **Expect**: Fatigue up by up to 40 (capped at 100); XP/level unchanged; energy down; daily drill counts incremented; success embed shows new fatigue.

## 2. Trade-off visibility

1. Open Training Drills for the same style of player.
2. **Expect**: Both Skill Drill and Recovery Session are presented with distinct outcomes before commit.

## 3. Already rested

1. Card at fatigue 100 → Recovery Session.
2. **Expect**: Clear “fully rested” rejection; no energy/cap spend.

## 4. Injured

1. Injured / in-hospital card → Recovery Session.
2. **Expect**: Rejected with Hospital guidance; no fatigue credit.

## 5. Capacity / energy

1. Exhaust club daily drills (20) or card log (5), or drain action energy.
2. **Expect**: Same class of messages as skill drills; Recovery cannot bypass.

## 6. Passive TG scaling (ops / SQL)

1. Note fatigue on two clubs (or same club before/after TG upgrade) with equal starting fatigue &lt; 100, not in hospital.
2. Run `process_daily_recovery` (or wait for 00:05 job).
3. **Expect**: Higher TG club gains `15 + TG×5`; hospital patients still use hospital daily amount.

## 7. Regressions

1. Skill drill on another card still grants XP and spends coins as before.
2. Competitive match: starters still drain; bench still +15.
3. Mentor / fusion / Allocate Skills unchanged.

## Contracts

- [process-recovery-session-rpc.md](./contracts/process-recovery-session-rpc.md)
- [daily-recovery-tg.md](./contracts/daily-recovery-tg.md)
- [development-recovery-ui.md](./contracts/development-recovery-ui.md)
- [fatigue-recovery-math.md](./contracts/fatigue-recovery-math.md)

# Tasks: Hospital ETA Backfill

**Input**: Design documents from `/specs/012-hospital-eta-backfill/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md  
**Hard dependency**: migration **056** (011 bases 1/4/7) already applied on target DB

**Tests**: New `tests/test_injury_eta_backfill.py` for pure fair-recalc helpers (required).

**Locked decisions** (research.md):
- Candidate ETA = `admission_date + new_total_days`; `final = LEAST(current, candidate)`; never lengthen
- Early discharge = full recovery clear (+25 fatigue), **not** manual untreated discharge
- One RPC `backfill_injury_eta_fairness()`; DMs **after** commit only
- Overflow untreated included in same RPC
- Migration `057_hospital_eta_backfill.sql`

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Confirm `056` applied; grep `hospital_patients`, `process_daily_recovery` discharge clear, `admission_date`, `injury_started_at`; confirm touch list matches `plan.md`

---

## Phase 2: Foundational — Pure math + tests

**Purpose**: Formula locked before SQL; enables independent verification of US1/US3 math

- [x] T002 [P] Add fair-recalc helpers to `packages/player_engine/player_engine/injury_math.py` per `contracts/fair-recalc-math.md` (`fair_hospital_final_eta`, `should_early_discharge`, `fair_overflow_remaining_days`; reuse `recovery_days_for_tier` / `BASE_RECOVERY_DAYS`)
- [x] T003 [P] Export new helpers from `packages/player_engine/player_engine/__init__.py` if the package re-exports injury math
- [x] T004 Create `tests/test_injury_eta_backfill.py`: never-lengthen, admission-anchored candidate, early-discharge gate, overflow remaining, idempotent final_eta

**Checkpoint**: `pytest tests/test_injury_eta_backfill.py -q` green

---

## Phase 3: US1 — Hospital ETA fair recalc (P1) 🎯 MVP

**Goal**: Active hospital stays shortened fairly; past new max → recovered discharge

**Independent Test**: RPC on DB with seeded active patient; panel ETA / cleared injury

- [x] T005 Create `supabase/migrations/057_hospital_eta_backfill.sql`: `CREATE OR REPLACE FUNCTION public.backfill_injury_eta_fairness() RETURNS JSONB` per `contracts/backfill-injury-eta-rpc.md` (hospital branch: LEAST ETA, sync `injury_recovery_days`, early recovery clear matching `process_daily_recovery` +25 fatigue); schema guard for function presence; extend `supabase/scripts/verify_required_schema.sql` with `function:backfill_injury_eta_fairness`
- [x] T006 [P] Add `scratch/apply_migration_057.py`: apply SQL then `SELECT backfill_injury_eta_fairness()`; print JSON summary
- [x] T007 [US1] Apply on target DB; confirm summary counts; spot-check active `hospital_patients.expected_recovery_date` never later than pre-pass; re-invoke RPC → idempotent (no ETA regression / no duplicate early discharges)

**Checkpoint**: FR-001–FR-006 hospital path live; SC-001–SC-004 for hospital

---

## Phase 4: US3 — Overflow untreated fair recalc (P2)

**Goal**: Non-hospital injured cards get shortened remaining days / clear when past new base

**Independent Test**: Covered by same RPC; unit tests already assert overflow math

- [x] T008 [US3] Ensure overflow branch in `057` / `backfill_injury_eta_fairness` implements `fair_overflow_remaining_days` semantics (min with current; clear at 0); include counts in JSON (`overflow_shortened`, `overflow_cleared`)
- [x] T009 [US3] After apply, spot-check `player_cards` with `injury_tier IS NOT NULL AND in_hospital = FALSE` remaining days ≤ pre-pass and ≤ new untreated base logic

**Checkpoint**: FR-007; can ship with US1 in same migration if T005 already included overflow (verify, don’t duplicate)

---

## Phase 5: US2 — Early-discharge Medical Update DMs (P2)

**Goal**: Managers notified when stars are recovered early; DM failure does not undo data

**Independent Test**: Dry-run notify with fixture list; closed-DM path logs and continues

- [x] T010 [P] [US2] Add `scratch/notify_hospital_eta_backfill.py` per `contracts/early-discharge-notify.md`: group `early_discharged` by `owner_id`, best-effort Discord DM, log failures
- [x] T011 [US2] Wire apply flow so notify runs **after** successful RPC commit (invoke from apply script with `--notify` flag **or** document manual second step in quickstart — pick one, keep YAGNI)

**Checkpoint**: FR-008 / SC-005; no slash command

---

## Phase 6: Polish

- [x] T012 [P] Reconcile `.specify/specs/v1.0.0/spec.md` (AC note: 012 mid-injury fairness pass after 011); brief note that 011 forward-only is superseded for open stays
- [x] T013 Update `change_log.md` — existing Hospital / untreated clocks recalculated fairly (time served credited; early discharge when past new max)
- [x] T014 Grep: no new slash commands; `backfill_injury_eta_fairness` has apply call site; run `pytest tests/test_injury_eta_backfill.py -q`; mark feature complete

---

## Dependencies

```text
T001 → T002 → T004
         T003 [P with T002]
              ↓
         T005 (RPC: hospital + overflow) → T006 → T007
              ↓
         T008–T009 (verify overflow if not already in T005)
              ↓
         T010 → T011 (notify after data)
              ↓
         T012–T014 Polish
```

- **MVP**: T002–T007 (math + hospital backfill applied). Overflow in T005 preferred so US3 is free.
- **Notify** is optional for data correctness; run before calling managers “done” on communication.

## Parallel opportunities

- T002 ∥ T003 after T001  
- T010 can be authored while T005–T007 run (different files)  
- T012 ∥ T013 after tests green  

## Out of scope (do not task)

- Changing 011 bases/drain/passive  
- Mass free heal / Store consumables  
- New slash commands or scheduler job  
- Rewriting historical discharged `hospital_patients` rows  
- Discord imports under `packages/`

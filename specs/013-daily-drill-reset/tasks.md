# Tasks: Daily Drill Cap Desync Fix

**Input**: Design documents from `/specs/013-daily-drill-reset/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required — `tests/test_api_errors.py` (per-card vs club mapping) + `tests/test_drill_caps.py` (effective count).

**Locked decisions** (research.md):
- Primary UX bug: `api_error_message` substring maps per-card limit → club toast
- Hub must use soft-reset display helper + select `daily_drill_reset_at`
- `process_stat_drill` null-safe soft-reset parity with recovery
- Repair from today’s `player_drill_daily_log` sum (not blind zero; not `clubs.*`)
- Migration `058_daily_drill_cap_desync.sql`; no nightly `process_daily_recovery` drill reset for MVP

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Grep `Daily drill limit reached`, `daily_drill_count`, `daily_drill_reset_at`, `api_error_message`, `process_stat_drill` soft-reset; confirm touch list matches `plan.md`

---

## Phase 2: US1/US2 foundation — Error mapping (P1) 🎯 MVP start

**Goal**: Per-card (5) errors never show as club (20) toast

**Independent Test**: `pytest tests/test_api_errors.py` with both exception strings

- [x] T002 [US1] Fix `apps/discord_bot/core/api_errors.py` per `contracts/api-error-drill-limits.md` (longest-key substring match, or per-card before club)
- [x] T003 [P] [US1] Add/extend `tests/test_api_errors.py`: per-card message → per-card copy; exact club message → club copy

**Checkpoint**: Reproduced “6/20 + club toast” case from per-card raise is fixed in unit tests

---

## Phase 3: US1 — Hub effective count (P1)

**Goal**: Training Drills `used/20` matches UTC soft-reset gate

**Independent Test**: `pytest tests/test_drill_caps.py`; open hub with yesterday’s count

- [x] T004 [P] [US1] Add `packages/player_engine/player_engine/drill_caps.py` (`effective_daily_drill_count`, `CLUB_DAILY_DRILL_LIMIT`) per `contracts/effective-daily-drill-count.md`
- [x] T005 [P] [US1] Export from `packages/player_engine/player_engine/__init__.py`
- [x] T006 [US1] Create `tests/test_drill_caps.py` (yesterday→0, today→count, null reset→0)
- [x] T007 [US1] Update `show_training_menu` in `apps/discord_bot/cogs/development_cog.py`: select `daily_drill_reset_at`; display `effective_daily_drill_count` with UTC `today`

**Checkpoint**: Hub never shows yesterday’s leftover as today’s used

---

## Phase 4: US2 — RPC soft-reset parity (P1)

**Goal**: Skill drill NULL/`reset_at` soft-reset matches recovery

**Independent Test**: Apply migration; club with `reset_at IS NULL` and high count can skill-drill

- [x] T008 [US2] Create `supabase/migrations/058_daily_drill_cap_desync.sql`: `CREATE OR REPLACE process_stat_drill` with `IF v_reset IS NULL OR v_reset < CURRENT_DATE` per `contracts/process-stat-drill-soft-reset.md` (base body from latest 043); verify recovery already null-safe
- [x] T009 [US2] Add `repair_daily_drill_counts()` in same migration per `contracts/repair-daily-drill-counts.md`; extend `supabase/scripts/verify_required_schema.sql` for the repair function
- [x] T010 [P] [US2] Add `scratch/apply_migration_058.py` (apply + invoke repair); optional thin `scratch/repair_daily_drill_counts.py` re-invoke

**Checkpoint**: Soft-reset + repair live on DB

---

## Phase 5: US3 — Stuck club repair verify (P2)

**Goal**: False club-cap blocks cleared using today’s log sum

**Independent Test**: Run repair; compare `daily_drill_count` to log sum; second run `updated=0`

- [x] T011 [US3] Apply `058` on target DB; run repair; spot-check reporter club (`discord_id` from logs if available) count vs today’s `player_drill_daily_log` sum
- [x] T012 [US3] Confirm idempotent re-run; document one-club SQL only as fallback in quickstart (already)

**Checkpoint**: FR-005 / SC-004–005

---

## Phase 6: Polish

- [x] T013 [P] Brief note in `.specify/specs/v1.0.0/spec.md` (drill soft-reset + friendly error mapping)
- [x] T014 Update `change_log.md` — Training Drills limit messages / daily counter clarity (player-facing)
- [x] T015 Run `pytest tests/test_api_errors.py tests/test_drill_caps.py -q`; grep no `clubs.daily_drills`; mark complete

---

## Dependencies

```text
T001 → T002 → T003          (error mapping MVP)
     → T004 → T005 → T006 → T007  (display; T004∥T005∥T006 after T001)
     → T008 → T009 → T010 → T011 → T012  (SQL + repair)
     → T013–T015 Polish
```

- **Ship bot ASAP after T002–T007** (fixes toast + hub without waiting on SQL).
- **T008–T012** required for NULL reset / stuck counters on Supabase.
- Bisup: `git pull` + `systemctl restart` after Python; apply `058` separately.

## Parallel opportunities

- T003 ∥ T004 after T002  
- T005 ∥ T006 with T004  
- T013 ∥ T014 after tests green  

## MVP

T002–T007 (mapping + hub) → then T008–T011 (DB) → polish

## Out of scope (do not task)

- `clubs.daily_drills_used`  
- Changing 20/5 caps  
- Nightly drill reset inside `process_daily_recovery` (MVP)  
- New slash commands  

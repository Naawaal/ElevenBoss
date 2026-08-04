# Tasks: Youth Academy V2 Acceptance and Soak

**Input**: `specs/052-youth-academy-v2-acceptance/`

## Phase 1 — Repository verification

- [x] T001 Run academy unit pytest suite; save evidence
- [x] T002 Grep: no Common-only gem path; no `/academy` command; no default exact POT in academy embeds; RPC callers present; no direct coin UPDATEs in 095
- [x] T003 Full `pytest` — note pre-existing non-YA failures; fix YA-related regressions
- [x] T004 Targeted ruff on YA V2 files

## Phase 2 — Target database

- [x] T005 Live config/caps/illegal-POT/RPC marker snapshot (`scratch/052_ya_v2_db_verify.py`)
- [x] T006 `verify_required_schema.sql` PASS on target

## Phase 3 — E2E scenarios

- [x] T007 Isolated-club E2E (`scratch/052_ya_v2_e2e_acceptance.py`) — intake/rarity/scout/promote/aging
- [x] T008 P1 fog-floor fix (migration **096**) — Deep/ladder never collapses to exact POT by default
- [x] T009 P1 season aging decay wire (migration **097**)

## Phase 4 — Monday soak

- [ ] T010 Capture first Monday V2 intake metrics into `soak-report.md` (PENDING next Monday UTC)
- [ ] T011 Optional second Monday cycle

## Phase 5 — Balance baseline

- [x] T012 Record baseline snapshot (over-cap clubs, range coverage) in acceptance record
- [ ] T013 Fill post-soak rarity mix / promote rates after T010

## Phase 6 — Defects

- [x] T014 Classify + remediate P0/P1 found during 052 (fog floor, obsolete tests, season decay gap)
- [x] T015 Document residual non-blocking issues

## Phase 7 — Closure

- [x] T016 Write `acceptance-record.md` with SC mapping + rollback
- [ ] T017 After Monday soak PASS: set decision **ACCEPT**, archive 051, close 052
- [x] T018 Sync SDD notes for 052; keep 051 specs as historical until T017

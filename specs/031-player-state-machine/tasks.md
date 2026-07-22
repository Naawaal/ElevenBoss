# Tasks: Player State Machine (US-42.2)

**Input**: Design documents from `/specs/031-player-state-machine/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: US-42.1 (`030` / migration `074`)

**Tests**: Required — `tests/test_card_state_derive.py`, `tests/test_card_state_matrix.py`, `tests/test_card_state_sql_guards.py` (+ smoke after 075).

**Locked decisions** (research.md):
- No `primary_state` column — derive from existing flags/tables
- Pure `packages/player_engine/card_state.py` + SQL `assert_card_action_allowed` in migration **`075_player_card_state_guards.sql`**
- Patch RPCs **only where audit finds gaps** — do not rewrite every RPC
- `TrainingBusy` only if `active_training` row exists; InAcademy is exclusive
- No new slash commands; no XP/economy pipe rewrite; races → 42.6; match settle tick → 42.4

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`…`[US5]` maps to spec user stories

---

## Phase 1: Setup — W0 RPC guard audit

**Purpose**: Know which RPCs already enforce the matrix before writing 075 patches

- [x] T001 Fill `specs/031-player-state-machine/contracts/rpc-guard-audit.md` by grepping latest definitions of listed RPCs under `supabase/migrations/` for `assert_not_in_match`, `assert_card_not_on_transfer_list`, `in_hospital`, `in_academy`, `active_evolutions`, `active_training`, `is_retired`, XI checks
- [x] T002 [P] Prioritize Gap=Yes rows into a short ordered list in `specs/031-player-state-machine/checklists/requirements.md` Notes (Critical: drill/evo/list/hospital/squad vs Listed+MatchLocked)
- [x] T003 [P] Confirm next migration is `075` (no `075_*.sql` yet) and touch list matches `specs/031-player-state-machine/plan.md` Structure

**Checkpoint**: Gap list ready; no code yet

---

## Phase 2: Foundational — Pure card state module (BLOCKS matrix stories) 🎯 MVP core

**Purpose**: Readable SoT for derive + `can_perform_action` matching spec §B.5 / `data-model.md` action codes

**⚠️ CRITICAL**: US1/US5 tests and hub hints depend on this module

- [x] T004 Create `packages/player_engine/player_engine/card_state.py` per `contracts/card-state-derive.md`: `CardStateFlags` (or TypedDict), `PrimaryState` literals including `InAcademy`, `derive_primary_state` with conflict priority Retired > SoldTransferred > Listed > Hospitalized > Evolving > TrainingBusy > InAcademy > InXI > RosterFree, `has_exclusive_conflict`, MatchLocked overlay helper
- [x] T005 Implement `can_perform_action(primary, match_locked, modifiers, action) -> tuple[bool, str]` in `packages/player_engine/player_engine/card_state.py` per `contracts/action-matrix.md` and spec §B.5 (including injury→block list/agent_sell; fatigue alone does not block list; MatchLocked blocks mutations, allows view)
- [x] T006 Export new symbols from `packages/player_engine/player_engine/__init__.py` (`derive_primary_state`, `can_perform_action`, constants/types as needed)

**Checkpoint**: Pure module importable; ready for US1 tests

---

## Phase 3: User Story 1 — One primary exclusive state (Priority: P1) 🎯 MVP

**Goal**: Derive always picks one primary; exclusive conflicts detectable; enter-B-while-A rejected at pure layer

**Independent Test**: SC-001/005 — parameterized derive + conflict fixtures

### Tests

- [x] T007 [P] [US1] Create `tests/test_card_state_derive.py`: each single busy flag → expected primary; InXI vs RosterFree; SoldTransferred when not owned; `has_exclusive_conflict` true when Listed+Hospitalized (etc.)

### Implementation

- [x] T008 [US1] Add `detect_exclusive_conflict` / document that `can_perform_action` returns Block with `state_conflict` style reason when conflict flags set — extend `card_state.py` if T004/T005 incomplete
- [x] T009 [P] [US1] Optional one-line note in `specs/029-game-integrity/spec.md` §5.1 that InAcademy is an exclusive primary (US-42.2 FR-020) — only if epic sketch still omits it

**Checkpoint**: Pure exclusive-state MVP demoable

---

## Phase 4: User Story 2 — Matrix agreement / SQL enforcement (Priority: P1)

**Goal**: Shared SQL assert encodes matrix; critical gap RPCs call it; pure matrix tests cover ≥12 cells

**Independent Test**: Matrix tests + assert present in 075 + wired into Gap Critical RPCs

### Tests

- [x] T010 [P] [US2] Create `tests/test_card_state_matrix.py`: parameterized Allow/Block cases (≥12) from spec §B.5 (Listed×drill Block, Listed×cancel_listing Allow, MatchLocked×assign_xi Block, RosterFree×list Allow, injury×list Block, fatigue-only×list Allow, Hospital×agent_sell Block, Evolving×start_evolution Block, etc.)

### Implementation

- [x] T011 [US2] Create `supabase/migrations/075_player_card_state_guards.sql`: `assert_card_action_allowed(p_owner_id BIGINT, p_card_id UUID, p_action TEXT)` per `contracts/sql-assert-card-action.md` (ownership, MatchLocked via `assert_not_in_match` for mutations, exclusive conflict, matrix raises `CARD_STATE: ...`); optional `card_primary_state(p_card_id)` debug helper; GRANT + migration DO guard
- [x] T012 [US2] In same migration (or immediately after assert): `CREATE OR REPLACE` only Gap=Critical RPCs from T002 to `PERFORM public.assert_card_action_allowed(...)` with correct `p_action` — minimum set must include paths that can drill/evo-start/list/admit/assign while Listed or MatchLocked if audit marked Gap
- [x] T013 [P] [US2] Extend `supabase/scripts/verify_required_schema.sql` for `assert_card_action_allowed` (+ optional `card_primary_state`)
- [x] T014 [P] [US2] Add `scratch/apply_migration_075.py` and `scratch/smoke_player_card_state_075.py` (function exists; smoke Block reason if test card available)
- [x] T015 [P] [US2] Create `tests/test_card_state_sql_guards.py`: assert `075_player_card_state_guards.sql` contains `assert_card_action_allowed` and `unique`/`CARD_STATE` or clear raise patterns; assert migration references at least one gap RPC name from audit

**Checkpoint**: Enforcement path exists for Critical gaps; matrix tests green

---

## Phase 5: User Story 3 — Safe transitions / remaining gaps (Priority: P1)

**Goal**: Enter/exit busy states remain atomic; remaining Gap=Yes RPCs from audit get assert calls; double-enter still unique-constrained

**Independent Test**: Audit Gap column all No (or accepted Intentional); unique indexes still protect double evo/list

### Implementation

- [x] T016 [US3] Wire remaining Gap=Yes RPCs from `contracts/rpc-guard-audit.md` into 075 (or `075` follow-up only if file too large — prefer one migration) with `assert_card_action_allowed` for academy/retire/fusion/allocate/recover/cancel paths as needed
- [x] T017 [P] [US3] Verify unique active evolution index / listing constraints still present (grep migrations); document in checklist Notes — no weakening
- [x] T018 [P] [US3] Confirm cancel listing / discharge / evo cancel paths do not require assert that would Block the exit action itself (cancel/discharge/claim Allowed per matrix)

**Checkpoint**: Transition exits safe; busy uniqueness intact

---

## Phase 6: User Story 4 — MatchLocked overlay (Priority: P2)

**Goal**: MatchLocked blocks mutations consistently via shared assert + existing `assert_not_in_match`

**Independent Test**: SC-003 — with lock, sampled mutation actions Block

### Tests

- [x] T019 [P] [US4] Extend `tests/test_card_state_matrix.py` with MatchLocked×(drill, start_evolution, assign_xi, list_transfer, claim_evolution) all Block; view_profile Allow

### Implementation

- [x] T020 [US4] Ensure `assert_card_action_allowed` invokes match-lock check for all mutation `p_action` values (not view); align exception family with existing `assert_not_in_match` messages where practical
- [x] T021 [P] [US4] Spot-check squad swap / formation RPC(s) call assert or `assert_not_in_match` — patch in 075 if Gap

**Checkpoint**: INV-17 covered in shared path

---

## Phase 7: User Story 5 — Modifiers (Priority: P2)

**Goal**: InjuryPlayOn blocks list/agent_sell; fatigue alone does not; Hospitalized ≠ injury modifier in derive

**Independent Test**: Spec US5 scenarios in pure tests

### Tests

- [x] T022 [P] [US5] Extend `tests/test_card_state_derive.py` / matrix: injury_tier set + not hospital → primary RosterFree (or InXI) but list/agent_sell Block; in_hospital → primary Hospitalized; high fatigue + list Allow

### Implementation

- [x] T023 [US5] Ensure SQL assert applies injury listing/agent_sell block even when primary is RosterFree (mirror pure); hospital primary still Blocks those actions
- [x] T024 [P] [US5] Do **not** add fatigue→list Block; add assert comment or test documenting intentional Allow

**Checkpoint**: Modifiers teachable and enforced

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Apply, verify, docs, lock

- [x] T025 Apply `075` via `scratch/apply_migration_075.py` when `DATABASE_URL` set; run `scratch/smoke_player_card_state_075.py`; note skip if unavailable
- [x] T026 [P] Run `pytest tests/test_card_state_derive.py tests/test_card_state_matrix.py tests/test_card_state_sql_guards.py -q`
- [x] T027 [P] Update `change_log.md` with busy-card / CARD_STATE player-facing notes (US-42.2)
- [x] T028 [P] Optional: minimal hub mapping of `CARD_STATE:` errors in one development/marketplace path — skip if RPC messages already clear
- [x] T029 Run `specs/031-player-state-machine/quickstart.md` Validations 0–4 as applicable; set `specs/031-player-state-machine/spec.md` Status → Locked
- [x] T030 Confirm zero new slash commands / no economy-XP pipe edits / no `primary_state` column; grep cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Audit**: Immediate — informs T012/T016
- **Phase 2 Pure module**: After or parallel with audit; **BLOCKS** US1 tests quality
- **Phase 3 US1**: After T004–T006
- **Phase 4 US2**: After pure module + audit; MVP enforcement
- **Phase 5 US3**: After T011 assert exists
- **Phase 6 US4**: After T011; tests can draft earlier
- **Phase 7 US5**: After T005 matrix logic
- **Phase 8 Polish**: After desired stories (min US1+US2)

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | Pure derive MVP |
| US2 | Phase 1+2 + 075 | Matrix + SQL |
| US3 | US2 assert | Remaining wires |
| US4 | US2 assert | Overlay |
| US5 | Phase 2 matrix | Modifiers |

### Parallel Opportunities

- T001 then T002 || T003
- T007 || T010 || T019 || T022 once pure API stable
- T013 || T014 || T015 after T011 written
- T017 || T018 after T016 planned
- T027 || T028 in Polish

### Parallel Example: After `card_state.py` exists

```text
Task: T007 tests/test_card_state_derive.py
Task: T010 tests/test_card_state_matrix.py
Task: T011 start 075 assert SQL
```

---

## Implementation Strategy

### MVP First (US1 + pure + Critical SQL)

1. Phase 1 audit  
2. Phase 2–3 pure derive + tests  
3. Phase 4 T011–T012 Critical RPC wires  
4. **STOP** — demo Listed blocks drill/evo; MatchLocked blocks assign  

### Incremental delivery

1. MVP pure + Critical asserts  
2. US3 remaining gaps  
3. US4/US5 modifier polish  
4. Apply/smoke/Lock  

### Suggested stop points

| Stop | When |
|------|------|
| Pure MVP | After T009 |
| Enforcement MVP | After T015 |
| Full child | After T030 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Same-file migration tasks (T011–T012, T016) = one authoring pass
- Do not implement US-42.3–42.10 here
- Do not add `packages/integrity` or new hubs
- Commit only when user requests

# Tasks: Match Concurrency & Squad Locking Integrity

**Input**: Design documents from `/specs/056-match-concurrency-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure & Migrations)

**Purpose**: Database migration and schema guard initialization

- [x] T001 Create migration file `108_match_concurrency_integrity.sql` in `supabase/migrations/108_match_concurrency_integrity.sql` containing `match_locks` table DDL update (`run_id` FK, `UNIQUE(discord_id)`), `assert_manager_match_available`, `start_friendly_match`, `start_single_manager_match`, and `reconcile_orphaned_match_locks`.
- [x] T002 Extend schema verification script in `supabase/scripts/verify_required_schema.sql` to include new RPC signatures and `match_locks` table guards.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared middleware and snapshot helpers that MUST be complete before user stories can lock matches or build runs

- [x] T003 [P] Implement `reject_if_in_match(interaction, db, *manager_ids)` helper in `apps/discord_bot/middleware/match_lock.py` using `assert_manager_match_available` RPC.
- [x] T004 [P] Implement `build_ephemeral_match_snapshot()` and enforce 11-card snapshot validation in `apps/discord_bot/core/match_runs.py`.

---

## Phase 3: User Story 1 - Cross-Mode Match Concurrency & Atomic Lock Acquisition (Priority: P1) 🎯 MVP

**Goal**: Prevent any manager from entering two active matches simultaneously by enforcing atomic run creation and lock acquisition across Friendly, Bot Battle, Ranked PvP, and League modes.

**Independent Test**: Initiate a Friendly match, attempt to enter a Bot Battle or Ranked queue from the same account, and verify immediate rejection.

### Implementation & Tests for User Story 1

- [x] T005 [P] [US1] Create unit and integration test suite in `tests/test_match_concurrency_integrity.py` verifying atomic lock acquisition, dual-match rejection across modes, and snapshot immutability.
- [x] T006 [US1] Wire atomic `start_friendly_match` RPC into Friendly challenge acceptance flow in `apps/discord_bot/cogs/battle_cog.py` (locking both managers in canonical ID order).
- [x] T007 [US1] Wire atomic `start_single_manager_match` RPC into Bot Battle and AI Practice flows in `apps/discord_bot/cogs/battle_cog.py`.
- [x] T008 [US1] Add `reject_if_in_match()` early command guards to Friendly creation, Friendly accept, Bot Battle, AI Practice, Ranked queue, and League manual kickoff in `apps/discord_bot/cogs/battle_cog.py`.

**Checkpoint**: At this point, User Story 1 (Cross-Mode Concurrency Prevention) is fully functional and testable independently as an MVP.

---

## Phase 4: User Story 2 - SQL-Enforced Squad Mutation Guards & UI Revalidation (Priority: P2)

**Goal**: Reject formation changes and player swaps at both Python and PL/pgSQL database levels while locked in an active match.

**Independent Test**: Acquire a match lock for a manager, invoke `set_formation_and_assignments` or `swap_squad_players` directly or from an open squad view, and verify SQL exception `manager_in_active_match` and UI button disablement.

### Implementation & Tests for User Story 2

- [x] T009 [P] [US2] Update PL/pgSQL stored procedures `set_formation_and_assignments` and `swap_squad_players` in `supabase/migrations/108_match_concurrency_integrity.sql` to check `match_locks` and raise `manager_in_active_match` (`P0001`) when locked.
- [x] T010 [US2] Update `apps/discord_bot/cogs/squad_cog.py` UI callbacks (`SquadFormationView`, `SquadSwapView`, `SquadHubView`) to catch `manager_in_active_match`, set `is_locked = True`, and disable formation/swap buttons with an ephemeral warning.
- [x] T011 [US2] Add unit tests in `tests/test_match_concurrency_integrity.py` verifying direct SQL procedure rejection and UI view disablement when locked.

**Checkpoint**: User Stories 1 AND 2 are complete and operational.

---

## Phase 5: User Story 3 - Terminal Lock Release & Hardened Startup Reconciliation (Priority: P3)

**Goal**: Retain locks during `streaming`, `completing`, and `recovering` states, release locks strictly upon terminal settlement (`completed`, `abandoned`), and harden bot startup reconciliation.

**Independent Test**: Simulate a bot crash mid-match during `streaming` status; verify startup recovery finds the run, resumes settlement, and releases the lock only upon completion.

### Implementation & Tests for User Story 3

- [x] T012 [P] [US3] Centralize terminal lock release in `apps/discord_bot/core/match_runs.py`, `apps/discord_bot/core/pvp_match.py`, and `apps/discord_bot/cogs/battle_cog.py` so locks are released ONLY on terminal statuses (`completed`, `abandoned`).
- [x] T013 [US3] Update `reconcile_orphaned_match_locks` in `108_match_concurrency_integrity.sql` and startup lifecycle in `apps/discord_bot/main.py` to run match recovery passes BEFORE orphan lock reconciliation.
- [x] T014 [US3] Add unit tests in `tests/test_match_concurrency_integrity.py` verifying terminal release, active state lock retention (`streaming`, `completing`), and restart recovery.

**Checkpoint**: All 3 user stories are complete and fully tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final schema verification and full regression suite execution

- [x] T015 Apply migration `108_match_concurrency_integrity.sql` locally via scratch script and run `python scratch/verify_schema_full.py`.
- [x] T016 Run full test suite (`pytest tests/test_match_concurrency_integrity.py -v`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion (migration applied).
- **User Story 1 (Phase 3)**: Depends on Phase 2.
- **User Story 2 (Phase 4)**: Depends on Phase 1 & Phase 2; can be implemented in parallel with US1.
- **User Story 3 (Phase 5)**: Depends on Phase 1 & Phase 2; independent of US1 and US2.
- **Polish (Phase 6)**: Depends on US1, US2, and US3 completion.

### Parallel Opportunities

- `T003` and `T004` can be developed in parallel in Phase 2.
- `T005` (US1 tests), `T009` (US2 SQL procedures), `T012` (US3 lock release) can run in parallel across user stories.

---

## Implementation Strategy

### MVP First (User Story 1)
1. Complete Phase 1 & 2 (Migration + Middleware/Snapshot helpers).
2. Complete Phase 3 (US1 Concurrency & Atomic RPCs).
3. Test US1 independently.

### Full Feature Delivery
1. Add US2 (SQL Squad Mutation Guards & Squad UI disablement).
2. Add US3 (Terminal Release & Startup Reconciliation).
3. Run Phase 6 validation suite.

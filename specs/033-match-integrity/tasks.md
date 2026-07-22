# Tasks: Match Integrity & Concurrency (US-42.4)

**Input**: Design documents from `/specs/033-match-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: `030`, `031`, `032`

**Tests**: Required — `tests/test_match_integrity_recovery.py`, `tests/test_match_integrity_sql_guards.py` (+ greps / extend `test_match_xp.py` as needed).

**Locked decisions** (research.md / match-path-audit.md):
- Keep economy key `match:{run_id}:{club_id}` and XP/`xp_applied_at` short-circuit — do not reinvent pipes
- Order: **pay → `complete_run` → present**; never `abandon_run` after successful rewards
- Migration **`077_match_integrity_guards.sql`**: `abandon_match_run`, `reconcile_orphaned_match_locks`
- Boot: complete-if-rewarded else abandon RPC; replace blind lock wipe with reconcile
- League human play: lock **both** humans; fail → abandon run
- Friendly stays sandbox; evo tick only inside `process_match_result`
- No new slash commands; no `026` calendar rewrite

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`…`[US5]` maps to spec user stories

---

## Phase 1: Setup — W0 audit confirm

**Purpose**: Confirm Critical gaps still match code before patching

- [x] T001 Re-confirm `specs/033-match-integrity/contracts/match-path-audit.md` Critical rows against current `apps/discord_bot/cogs/battle_cog.py` (bot finalize except → abandon) and `apps/discord_bot/core/match_recovery.py` (blind lock wipe)
- [x] T002 [P] Note Critical ordered fix list in `specs/033-match-integrity/checklists/requirements.md` Notes
- [x] T003 [P] Confirm next migration is `077` (no `077_*.sql` yet) and touch list matches `plan.md` Structure

**Checkpoint**: Audit current; no code yet

---

## Phase 2: Foundational — Recovery classifier helper (optional but preferred)

**Purpose**: Pure branch table for interrupted-run decisions (testable)

- [x] T004 [P] Add `classify_interrupted_run(*, status: str, rewards_applied: bool) -> Literal["complete","abandon","noop"]` in `packages/player_engine/player_engine/match_integrity.py` (or equivalent thin module) per `contracts/match-run-lifecycle.md`
- [x] T005 Export from package `__init__.py` if new module added; skip export if helper stays private to `match_recovery.py` with unit-tested pure function in `tests/`

**Checkpoint**: Classifier testable

---

## Phase 3: User Story 1 — Settle once / present retry (Priority: P1) 🎯 MVP

**Goal**: One durable reward per run; present failure does not abandon or re-pay

**Independent Test**: SC-001/002

### Tests

- [x] T006 [P] [US1] Create `tests/test_match_integrity_recovery.py`: classify interrupted — rewards_applied+streaming → complete; no rewards → abandon; already completed → noop
- [x] T007 [P] [US1] Extend or add assertion that economy/XP idempotency keys remain documented (reuse existing economy/match_xp tests if present; else minimal key-format unit assert)

### Implementation

- [x] T008 [US1] In `apps/discord_bot/cogs/battle_cog.py` bot path: after successful rewards, call `complete_run` **before** Discord finalize; on finalize exception → log + present-retry / user message — **do not** `abandon_run`
- [x] T009 [US1] Same ordering for league reward → durable complete/fixture mark → present in `battle_cog` / league finalize path (grep `apply_league_human_rewards` / `complete_run` call sites)
- [x] T010 [P] [US1] Grep `abandon_run` after reward success in `battle_cog.py` — zero remaining Critical cases

**Checkpoint**: Present-after-settle MVP

---

## Phase 4: User Story 2 — Lock lifecycle (Priority: P1)

**Goal**: Both league humans locked; terminals clear locks; INV-17 holds

**Independent Test**: SC-003

### Implementation

- [x] T011 [US2] `execute_league_match` in `battle_cog.py`: `acquire_match_lock` for **both** human clubs (parity with `league_lifecycle_engine`); release both in `finally`
- [x] T012 [US2] Create `supabase/migrations/077_match_integrity_guards.sql`: `abandon_match_run(p_run_id UUID, p_reason TEXT DEFAULT NULL)` per `contracts/lock-and-abandon.md` (terminal status + release home/away/active locks; no-op if already completed)
- [x] T013 [US2] Same migration: `reconcile_orphaned_match_locks()` — delete locks with no streaming/completing run referencing club
- [x] T014 [P] [US2] Extend `supabase/scripts/verify_required_schema.sql` for both new functions
- [x] T015 [US2] On hard fail in `execute_league_match` after run created: call `abandon_match_run` (RPC or helper) so run is not left streaming while unlocked
- [x] T016 [P] [US2] Create `tests/test_match_integrity_sql_guards.py`: 077 contains `abandon_match_run`, `reconcile_orphaned_match_locks`, lock release patterns

**Checkpoint**: Lock/abandon RPC exists; league dual-lock wired

---

## Phase 5: User Story 3 — DB-authoritative settlement / INV-10 (Priority: P1)

**Goal**: Rewards tied to durable settle; evo tick only in pipe; friendly sandbox

### Tests

- [x] T017 [P] [US3] Add grep/assert test: `tick_evolution_match_progress` has **zero** callers under `apps/`
- [x] T018 [P] [US3] Assert friendly path in `battle_cog` does not call `process_match_result` / `apply_match_economy` (source or unit guard)

### Implementation

- [x] T019 [US3] Confirm/document in checklist that `process_match_result` remains sole evo tick site — no new tick call sites introduced by this feature
- [x] T020 [P] [US3] Do **not** change XP/economy pipe signatures unless required for ordering — keep keys

**Checkpoint**: INV-10 locked by tests

---

## Phase 6: User Story 4 — Restart / abandon recovery (Priority: P2)

**Goal**: Boot recovery complete-if-rewarded; targeted lock reconcile; SC-005

### Implementation

- [x] T021 [US4] Rewrite `apps/discord_bot/core/match_recovery.py` bot/friendly interrupted handling: if rewards already applied for run → `complete_run`; else `abandon_match_run` RPC
- [x] T022 [US4] Replace blind `match_locks` delete-all with `reconcile_orphaned_match_locks` RPC after run recovery loop
- [x] T023 [P] [US4] Thin wrappers in `apps/discord_bot/middleware/match_lock.py` or `match_runs.py` for `abandon_match_run` / `reconcile_orphaned_match_locks` if not already RPC-callable cleanly
- [x] T024 [P] [US4] League recovery early-return soft-stall: if cannot resume, call `abandon_match_run` + reconcile rather than leave streaming unlocked (minimal harden)
- [x] T025 [P] [US4] Optional APScheduler stuck-lock sweeper — **skip** unless trivial; boot reconcile is enough for MVP

**Checkpoint**: Restart recovery matches contracts

---

## Phase 7: User Story 5 — Match types distinct (Priority: P2)

**Goal**: Type matrix regression coverage

### Tests

- [x] T026 [P] [US5] Document/assert type matrix in `tests/test_match_integrity_recovery.py` or dedicated table test: bot/league rewardable; friendly not

### Implementation

- [x] T027 [P] [US5] Spot-check friendly still writes logs only — no accidental reward wire in this diff

**Checkpoint**: Type matrix intact

---

## Phase 8: Polish & Cross-Cutting

- [x] T028 Add `scratch/apply_migration_077.py` and `scratch/smoke_match_integrity_077.py` (functions exist; optional abandon on synthetic run if safe)
- [x] T029 Apply `077` when `DATABASE_URL` set; run smoke; note skip if unavailable
- [x] T030 [P] Run `pytest tests/test_match_integrity_recovery.py tests/test_match_integrity_sql_guards.py -q` (+ related match_xp if touched)
- [x] T031 [P] Update `change_log.md` only if managers see new recovery/lock copy; else note enforcement-only in checklist
- [x] T032 Run `quickstart.md` Validations 0–4 as applicable; set `specs/033-match-integrity/spec.md` Status → Locked
- [x] T033 Confirm zero new slash commands / no economy-XP pipe redesign / no `026` edits / no friendly faucet; grep cleanup
- [x] T034 [P] Pointer in `.specify/specs/v1.0.0/spec.md` (near match/US-22) to `specs/033-match-integrity` (US-42.4)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: Immediate
- **Phase 2**: Optional parallel with Phase 1
- **Phase 3 US1**: Critical MVP — can start before 077 if only Python ordering; prefer T008–T010 early
- **Phase 4 US2**: 077 + dual lock — blocks clean US4
- **Phase 5 US3**: Tests anytime after audit
- **Phase 6 US4**: After T012–T013
- **Phase 7–8**: After US1+US2 minimum

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 1 | Present/settle order |
| US2 | US1 helpful; 077 | Locks |
| US3 | Tests | INV-10 |
| US4 | US2 RPCs | Boot recovery |
| US5 | US3 | Type matrix |

### Parallel Opportunities

- T001 then T002 || T003
- T006 || T007 || T017 || T018 once classifier API stable
- T014 || T016 after T012–T013 written
- T031 || T034 in Polish

### MVP stop

After T010 + T011 + T015 (present-after-settle + dual league lock + fail abandon) even if 077 still drafting — then finish T012–T022 before Lock.

---

## Implementation Strategy

1. Phase 1 audit confirm  
2. Phase 3 bot/league present-after-settle (US1)  
3. Phase 4 dual lock + 077 abandon/reconcile (US2)  
4. Phase 6 boot recovery (US4)  
5. Tests + changelog + Lock  

### Suggested stop points

| Stop | When |
|------|------|
| Present MVP | After T010 |
| Lock RPC MVP | After T016 |
| Full child | After T034 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Same-file `battle_cog` / `match_recovery` tasks = careful sequential edits
- Soft career-stats idempotency deferred unless one-liner
- Commit only when user requests

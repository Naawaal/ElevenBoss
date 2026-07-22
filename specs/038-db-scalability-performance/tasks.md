# Tasks: Database Scalability & Performance Architecture (US-43)

**Input**: Design documents from `/specs/038-db-scalability-performance/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by plan.md — `tests/test_config_cache.py`, `tests/test_idempotent_outcome.py`, `tests/test_db_retry.py`; extend economy/pack tests for FR-006a where touched.

**Locked decisions** (research.md + Clarifications 2026-07-22):
- Principle II kept — no `asyncpg`; thin RPCs; formulas in packages
- Process-local TTL config cache in Phase 0–1; economy tunables need shared/active invalidation under multi-instance (FR-012)
- Idempotent Outcome: `applied` | `already_applied` + payload; map legacy `replay: true`
- No Redis / job locks / pack-claim key until Phase 2–3 gates
- No new slash commands; cite US-42.7/42.8/42.9 on mutating PRs
- Next migrations start at **080**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`…`[US6]` maps to spec user stories

## Path Conventions

- Apps: `apps/discord_bot/`
- Migrations: `supabase/migrations/`
- Tests: `tests/` at repo root
- Specs: `specs/038-db-scalability-performance/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and measurement harness before product code

- [x] T001 Grep `acreate_client`, `get_game_config`, `get_game_config_int`, `get_game_config_numeric`, `show_training_menu`, `show_hub`, `show_store`, `claim_daily_pack`, `scheduler_jobs`, `replay` across `apps/discord_bot/` and `supabase/migrations/`; confirm touch list matches `plan.md` Project Structure
- [x] T002 [P] Create `scratch/baseline_hub_roundtrips.py` to count remote `execute()` round-trips and wall time for HP-1…HP-6 entrypoints listed in `specs/038-db-scalability-performance/contracts/hot-path-catalog.md` (mock or instrumented path OK if live Discord unavailable)
- [x] T003 [P] Create `scratch/explain_hot_paths.py` skeleton writing before/after plan text under `scratch/explain_snapshots/` per `contracts/query-plan-gate.md`
- [x] T004 Confirm `apps/discord_bot/db/client.py` is the sole production `acreate_client` path (document any exceptions found in T001 notes)

**Checkpoint**: Measurement scripts exist; singleton confirmed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared cache / retry / outcome / signals modules that ALL stories use

**⚠️ CRITICAL**: No hub consolidation or mutation UX work until T005–T012 land

- [x] T005 Create process-local TTL cache in `apps/discord_bot/core/config_cache.py` (`get`/`set`/`invalidate`/`invalidate_prefix`, default TTL 300s, key pattern `cfg:{key}` per `contracts/cache-policy-and-keys.md`)
- [x] T006 [P] Create `apps/discord_bot/core/idempotent_outcome.py` with Pydantic (or TypedDict) `IdempotentOutcome` and `parse_idempotent_outcome` mapping `replay: true` → `already_applied` per `contracts/idempotent-outcome.md`
- [x] T007 [P] Create `apps/discord_bot/core/db_retry.py` with bounded exponential backoff + jitter for transient transport/5xx only; never retry non-idempotent mutations without a key
- [x] T008 [P] Create `apps/discord_bot/core/perf_signals.py` with in-process counters for hub wall ms, round-trips, cache hit/miss, retries; structured log helpers (`perf.hub`, `perf.cache`, `perf.retry`) per `contracts/observability-signals.md`
- [x] T009 Wire `get_game_config`, `get_game_config_int`, `get_game_config_numeric` in `apps/discord_bot/core/economy_rpc.py` through `config_cache` (read-through; preserve existing defaults on failure)
- [x] T010 [P] Add `tests/test_config_cache.py` covering TTL expiry, invalidate, and hit/miss counters
- [x] T011 [P] Add `tests/test_idempotent_outcome.py` covering `applied` / `already_applied` / `rejected` and legacy `replay` mapping
- [x] T012 [P] Add `tests/test_db_retry.py` covering retry-on-transient, no-retry-on-4xx-business, max attempts

**Checkpoint**: Foundation ready — user stories can proceed

---

## Phase 3: User Story 1 — Commands feel fast (Priority: P1) 🎯 MVP

**Goal**: Hot hubs (`/development` Training Drills + hub, `/store`) respond within SC-001 and cut remote round-trips ≥50% (SC-004)

**Independent Test**: Fill baseline/after columns for HP-1 and HP-2 in `contracts/hot-path-catalog.md`; light-load p95 ≤2s; Training Drills still shows correct costs/energy

### Tests for User Story 1

- [x] T013 [P] [US1] Extend or add assertion helpers in `tests/test_config_cache.py` (or new `tests/test_hub_roundtrip_guards.py`) that document expected max remote calls for Training Drills config load after cache warm (contract: cold may batch, warm ≈ 0 config RPCs)

### Implementation for User Story 1

- [x] T014 [US1] Run `scratch/baseline_hub_roundtrips.py` for HP-1, HP-2, HP-3; paste Baseline RTs/p95 into `specs/038-db-scalability-performance/contracts/hot-path-catalog.md`
- [x] T015 [US1] Run EXPLAIN candidates for `league_fixtures` season/matchday filters and any club `economy_ledger` scans via `scratch/explain_hot_paths.py`; record in `contracts/query-plan-gate.md` log table
- [x] T016 [US1] Create `supabase/migrations/080_scalability_indexes.sql` with **only** indexes justified by T015 (candidates: `league_fixtures (season_id, matchday)` and/or partial unplayed; `economy_ledger (club_id, created_at DESC)`); include brief comment citing EXPLAIN
- [x] T017 [P] [US1] Add `scratch/apply_migration_080.py` following `scratch/apply_migration_079.py` pattern
- [x] T018 [US1] Apply 080 locally/remote via scratch script; re-run EXPLAIN after; update query-plan log Decision column
- [x] T019 [US1] Optional: create `supabase/migrations/081_game_config_batch.sql` implementing `get_game_config_many(p_keys text[])` → `jsonb`; extend `supabase/scripts/verify_required_schema.sql` guard for the function
- [x] T020 [US1] If T019 ships: add `get_game_config_many` helper in `apps/discord_bot/core/economy_rpc.py` that fills `config_cache` in one round-trip
- [x] T021 [US1] Consolidate `show_training_menu` in `apps/discord_bot/cogs/development_cog.py` to use cached/batch config and avoid redundant `sync_action_energy` when recently synced; instrument with `perf_signals`
- [x] T022 [US1] Consolidate `show_hub` in `apps/discord_bot/cogs/development_cog.py` to reduce sequential selects/RPCs (optional thin `get_development_hub_bundle` in `supabase/migrations/082_hub_dashboard_loads.sql` only if gather/cache insufficient for SC-004); instrument with `perf_signals`
- [x] T023 [US1] Consolidate `show_store` in `apps/discord_bot/cogs/store_cog.py` to share cached config / avoid duplicate energy-config RPCs; instrument with `perf_signals`
- [x] T024 [US1] Re-measure HP-1/HP-2/(HP-3); update After columns in `contracts/hot-path-catalog.md`; confirm SC-004 ≥50% RT drop and SC-001 light-load target

**Checkpoint**: US1 MVP — Training Drills + Development hub (and Store if touched) meet latency/RT gates

---

## Phase 4: User Story 2 — Growth without a rewrite (Priority: P1)

**Goal**: Architecture stays stable toward large scale; Phase gates prevent premature Redis/sharding/`asyncpg`

**Independent Test**: Checklist in plan Complexity/roadmap shows Phase 3+ items still gated; grep finds no application `asyncpg`/`psycopg` data path; singleton client only

### Implementation for User Story 2

- [x] T025 [P] [US2] Add short US-43 cross-link + phase-gate summary to `.specify/specs/v1.0.0/plan.md` (and `spec.md` only if required by AGENTS SDD rule) pointing at `specs/038-db-scalability-performance/`
- [x] T026 [P] [US2] Document in `AGENTS.md` Section 6/8 a one-paragraph pointer: performance work follows US-43; no parallel XP/coin pipes; Principle II unchanged
- [x] T027 [US2] Add `specs/038-db-scalability-performance/contracts/phase-gate-checklist.md` listing Phase 2/3/4 exit criteria from spec roadmap (SC-002, SC-006, FR-012 multi-instance, Redis waiver rules)
- [x] T028 [US2] Grep CI/local: zero new `import asyncpg` / raw pooler usage under `apps/`; fail task if found outside scratch

**Checkpoint**: Growth path is documented and enforceable without rewriting game logic

---

## Phase 5: User Story 3 — Spikes do not corrupt economy/inventory (Priority: P1)

**Goal**: Retries and double-invokes never double-grant; successful-retry UX uses `already_applied` (FR-006a / SC-003)

**Independent Test**: Scripted double-invoke on a keyed mutation shows one grant; second UI is success/`already_applied` not raw 409/500

### Tests for User Story 3

- [x] T029 [P] [US3] Add pack/idempotency cases to `tests/test_economy_flows.py` or new `tests/test_pack_claim_idempotency.py` asserting second call with same key does not double-grant (mock RPC JSON or SQL contract grep if DB unavailable)

### Implementation for User Story 3

- [x] T030 [US3] Wire at least one live mutation path in `apps/discord_bot/cogs/store_cog.py` (or energy refill purchase) through `parse_idempotent_outcome` so `replay`/`already_applied` renders success UI
- [x] T031 [US3] Create `supabase/migrations/083_pack_claim_idempotency.sql` (number may shift if 081/082 used): extend `claim_daily_pack` with `p_idempotency_key`, durable unique enforcement, return FR-006a envelope (`applied`/`already_applied`/`rejected` + `data`); `DROP FUNCTION` old overload first if signature changes
- [x] T032 [P] [US3] Add `scratch/apply_migration_083.py` (match actual migration number)
- [x] T033 [US3] Update store/pack client call sites in `apps/discord_bot/` to pass idempotency key (prefer Discord `interaction.id` or `daily_pack:{club_id}:{utc_date}` per data-model) and handle envelope without false-failure UX
- [x] T034 [US3] Extend `supabase/scripts/verify_required_schema.sql` for new/replaced `claim_daily_pack` signature + any new ledger constraint
- [x] T035 [US3] Update `specs/029-game-integrity/contracts/idempotency-anchor-map.md` pack row to note key pattern + FR-006a envelope (US-43 overlay)

**Checkpoint**: SC-003 evidenced for pack/store path; INV-08 not weakened

---

## Phase 6: User Story 4 — Operators can see health (Priority: P2)

**Goal**: Ops can answer “are we healthy?” from published signals within 5 minutes (SC-005)

**Independent Test**: Trigger HP-1 twice; logs show `perf.hub` + cache hit; thresholds in `contracts/observability-signals.md` match code constants

### Implementation for User Story 4

- [x] T036 [US4] Ensure HP-1/HP-2/HP-3 entrypoints emit `perf_signals` logs (complete any gaps left from T021–T023) in `apps/discord_bot/cogs/development_cog.py` and `store_cog.py`
- [x] T037 [US4] Increment round-trip counter at a single choke point (prefer thin wrapper used by hot paths, or documented manual marks) so SC-004 evidence is automatable
- [x] T038 [P] [US4] If an existing admin/stats surface exists in `apps/discord_bot/`, expose read-only snapshot from `perf_signals`; otherwise document log-only watch procedure in `contracts/observability-signals.md` (no new slash command)
- [x] T039 [US4] Align alert threshold constants/comments in `perf_signals.py` with `contracts/observability-signals.md` table

**Checkpoint**: SC-005 dry-run possible from logs (or admin surface)

---

## Phase 7: User Story 5 — Background jobs once-only when scaled out (Priority: P2)

**Goal**: Multi-instance safe job ownership (FR-016 / SC-006) — **gated**; implement only when multi-instance is planned

**Independent Test**: Two-process drill (or simulated double-scheduler) → one durable `daily_recovery` (or chosen job) per window

### Implementation for User Story 5

- [x] T040 [US5] Design claim key list for all DB-writing jobs in `apps/discord_bot/core/scheduler_jobs.py` + `apps/discord_bot/tasks/` (`job:{name}:{window}`) in `specs/038-db-scalability-performance/contracts/job-claim-catalog.md`
- [x] T041 [US5] Create migration `supabase/migrations/08x_job_claim_locks.sql` reusing `league_operation_runs` pattern or new `job_claims` table per `data-model.md` §3.5; RLS if Data API exposed
- [x] T042 [US5] Add claim/release helpers in `apps/discord_bot/core/job_claims.py` (or extend league acquire helper) using unique `operation_key` insert
- [x] T043 [US5] Wrap durable side effects in `daily_recovery_job` and at least one other high-risk job (`weekly_payroll_job` or `league_lifecycle_wake_job`) with claim-before-write / skip-on-conflict
- [x] T044 [P] [US5] Add `tests/test_job_claims.py` (or extend `tests/test_job_catalog_guards.py`) proving duplicate claim does not double-apply
- [x] T045 [US5] Document SC-006 two-process drill steps in `quickstart.md` Phase 3 preview section; do **not** enable multi-instance deploy until drill passes

**Checkpoint**: Job ownership ready before horizontal scale

---

## Phase 8: User Story 6 — Phased delivery prefers simple gains first (Priority: P3)

**Goal**: Advanced complexity (Redis, write-behind, sharding) stays gated until metrics demand it

**Independent Test**: Phase-gate checklist shows Redis/sharding blocked; Cache Key Catalog complete before any shared-cache PR

### Implementation for User Story 6

- [x] T046 [P] [US6] Tag priced economy keys in `contracts/cache-policy-and-keys.md` with an explicit “priced” column checklist (drill/refill/pack/wage keys from `game_config` usage grep)
- [x] T047 [US6] Add stub interface note (not implementation) for Phase 3 shared-cache adapter behind `config_cache` in `apps/discord_bot/core/config_cache.py` docstring — process backend default; shared backend requires FR-012
- [x] T048 [US6] Verify `plan.md` / `contracts/phase-gate-checklist.md` still defer write-behind for coins/XP and sharding; amend if any task drifted

**Checkpoint**: YAGNI gates intact

---

## Phase 9: Polish & Cross-Cutting

**Purpose**: Validation, schema guards, player-facing notes only if UX changed

- [x] T049 [P] Run `pytest tests/test_config_cache.py tests/test_idempotent_outcome.py tests/test_db_retry.py` (plus US3 tests) and fix failures
- [x] T050 [P] Run `quickstart.md` sections 1–6 checklist; tick boxes in `specs/038-db-scalability-performance/quickstart.md`
- [x] T051 Extend `supabase/scripts/verify_required_schema.sql` for any shipped 080–083 functions/tables still missing guards
- [x] T052 If manager-visible behavior changed (faster hubs alone = optional): brief note in `change_log.md`; if pack retry UX changed, required
- [x] T053 Mark `specs/038-db-scalability-performance/spec.md` Status **Implemented** for shipped waves only (leave Phase 3/4 items explicit backlog if deferred)
- [x] T054 [P] Re-read AGENTS verification checklist §13 for US-43 PR: no discord-in-packages, no XP/coin bypass, migration applied, callers grepped

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: immediate
- **Foundational (Phase 2)**: after Setup — **BLOCKS** US1–US6 product work
- **US1 (Phase 3)**: after Foundational — **MVP**
- **US2 (Phase 4)**: after Foundational; can parallel with US1 (docs-heavy)
- **US3 (Phase 5)**: after Foundational; ideally after US1 Store touch to reuse instrumentation
- **US4 (Phase 6)**: after US1 hub instrumentation (T021–T023) or complete gaps
- **US5 (Phase 7)**: **gated** — after MVP; only when multi-instance scheduled
- **US6 (Phase 8)**: after US1 cache lands; before any Redis PR
- **Polish (Phase 9)**: after desired stories for the ship wave

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP; drives SC-001/SC-004 |
| US2 | Phase 2 | Parallel OK with US1 |
| US3 | Phase 2 (+ T006) | Pack migration independent of hub RT goals |
| US4 | US1 instrumentation | Completes SC-005 |
| US5 | Phase 2 + multi-instance decision | Do not block MVP |
| US6 | US1 cache + US2 gates | Process discipline |

### Parallel Opportunities

- T002/T003; T006/T007/T008; T010/T011/T012
- T017 with docs T025/T026 while 080 applies
- T032 with client work sequencing carefully after migration exists
- US2 docs (T025–T027) parallel to US1 measurement (T014–T015)

---

## Parallel Example: Foundational

```text
T006 idempotent_outcome.py
T007 db_retry.py
T008 perf_signals.py
T010–T012 unit tests (after respective modules exist)
```

## Parallel Example: User Story 1 (post-baseline)

```text
T017 apply_migration_080.py   # while EXPLAIN log updated
T019–T020 batch config         # optional track
# then serial: T021 → T022 → T023 → T024
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup  
2. Phase 2 Foundational  
3. Phase 3 US1 (baseline → indexes → cache-driven Training Drills + hubs → remeasure)  
4. **STOP** — validate SC-001/SC-004 via hot-path catalog  
5. Ship MVP; schedule US3 pack idempotency as next integrity wave  

### Incremental Delivery

1. MVP (US1) → perceived speed  
2. US2 docs gates → governance  
3. US3 FR-006a pack → integrity UX  
4. US4 signals → ops  
5. US5/US6 only when scaling out  

### Suggested MVP scope

**T001–T024** (Setup + Foundational + US1). Defer T040–T045 until multi-instance is a real deploy goal.

---

## Notes

- Citation on mutating PRs: **US-43** + relevant **US-42.7 / 42.8 / 42.9**
- Migration numbers 081–083 may shift if optional batch/dashboard RPCs skipped — keep sequence contiguous; update task file paths when numbering finalizes
- Prefer deletion/skip of optional 081/082 if cache alone hits SC-004 (YAGNI)
- Never invent parallel coin/XP pipes for speed

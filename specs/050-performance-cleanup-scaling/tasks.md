# Tasks: Performance, Cleanup & Scalability Hardening

**Input**: Design documents from `/specs/050-performance-cleanup-scaling/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included where FR-034 / plan require structural gates — `tests/test_leaderboard_page_budget.py`, `tests/test_market_browse_server_filter.py`, `tests/test_hub_round_trip_budgets.py`, cache backend tests. Load scripts are ops validation (staging), not Discord load generation.

**Locked decisions** (research.md / plan.md):
- Extend existing `perf_signals`, `config_cache`, singleton client, `job_claims` — do not replace
- Migrations **090+** (additive RPCs first); indexes only after EXPLAIN (`091`/`092`/`093`)
- Do **not** raise HTTP pool before Phase 2 round-trip cuts
- Development hub-state RPC is **read-only** (no `ensure_pending_legendary` inside read)
- Match V2 deletion / Mentor flag removal = separate deploys from hot-path RPCs (US7)
- Cite **US-42.7 / 42.8 / 42.9** + **US-43**; no parallel XP/economy pipes
- Page sizes stay UX-stable: division **10**, Transfer Board **25**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US8 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inventories and scaffolding before coding hot paths

- [x] T001 Append feature-flag inventory (Mentor env, `match_engine_v3_*`, `league_dynamics_enabled`, `league_automation_enabled`, lifecycle jobs) to `specs/050-performance-cleanup-scaling/research.md` with file:line call sites
- [x] T002 [P] Confirm next migration number is **090+** (latest `089_*`); note proposed filenames in `specs/050-performance-cleanup-scaling/plan.md` Structure section if drifted
- [x] T003 [P] Create `scripts/load/` directory with README stub pointing at staging-only usage per `specs/050-performance-cleanup-scaling/quickstart.md`
- [x] T004 [P] Grep confirm zero app imports of `training` / `training_engine` across `apps/`, `packages/`, `tests/`, `scripts/`, `scratch/`; record results in research appendix

**Checkpoint**: Inventories done; safe to change deps and shared helpers

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared helpers used by multiple stories — **MUST land before US3–US6 RPC wiring**

**⚠️ CRITICAL**: US3–US6 implementation waits on cursor helper + instance identity. US1/US2 may start in parallel with this phase once T005–T007 exist (or immediately for pure cleanup greps).

- [x] T005 Add process `instance_id` helper (env `INSTANCE_ID` or hostname+pid fallback) in `apps/discord_bot/core/instance_id.py` and include it in structured logs from `apps/discord_bot/main.py`
- [x] T006 [P] Implement opaque keyset cursor encode/decode helpers in `apps/discord_bot/core/cursors.py` per `contracts/cursor-pagination.md` (division, global LP, market created_at/price)
- [x] T007 [P] Create `requirements-ops.txt` (move/list `asyncpg` and note `psycopg` for scratch apply scripts) and `requirements-dev.txt` (pytest / pytest-asyncio if not already isolated); leave production bot deps in `requirements.txt`
- [x] T008 [P] Make Supabase HTTP pool sizes env-configurable in `apps/discord_bot/db/client.py` (`SUPABASE_HTTP_MAX_CONNECTIONS`, `KEEPALIVE`, `TIMEOUT`) **without changing defaults** (20/5)
- [x] T009 Document round-trip budget table baseline placeholders filled-from-code estimates in `specs/050-performance-cleanup-scaling/contracts/round-trip-budgets.md` (Division unbounded, Board fetch-50, etc.)

**Checkpoint**: Foundation ready — measurement, cleanup, and RPC stories can proceed

---

## Phase 3: User Story 1 — Operators can see hub speed (Priority: P1) 🎯 MVP-A

**Goal**: Extend `perf_signals`, wire Sentry, owner-only Performance panel, start baseline capture

**Independent Test**: `/admin` Performance (or log snapshot) shows per-hub count/p50/p95/p99/RTs/cache/errors; Sentry init only when DSN set; 24h+ capture possible

**Contracts**: [observability.md](./contracts/observability.md)

### Implementation for User Story 1

- [x] T010 [US1] Extend `apps/discord_bot/core/perf_signals.py`: 1-minute buckets per hub/command, p99, 429/5xx counters, round-trip/retry aggregation, `instance_id` on `snapshot()`, periodic flush to structured logs (no per-command DB rows)
- [x] T011 [P] [US1] Add `apps/discord_bot/core/sentry_setup.py`: init `sentry-sdk` when `SENTRY_DSN` set; safe tags only (command/hub, instance_id, guild_id, rpc_name, latency_class, error_category)
- [x] T012 [US1] Call `sentry_setup` from `apps/discord_bot/main.py` at startup; ensure missing DSN is a no-op
- [x] T013 [US1] Extend owner-only `/admin` Performance panel in `apps/discord_bot/cogs/admin_cog.py` (or existing admin surface) consuming `perf_signals.snapshot()` — no new public slash command
- [x] T014 [US1] Wire `inc_round_trip` / status class hooks on data-client retry paths in `apps/discord_bot/core/db_retry.py` (create thin wrapper if missing) for transient 429/5xx on **safe reads only**
- [x] T015 [US1] Extend `scratch/baseline_hub_roundtrips.py` (or create if absent) to count awaits for `leaderboard`, `marketplace` hub/board/sell, `development` `show_hub`; write results into `contracts/round-trip-budgets.md` Phase 0 columns
- [x] T016 [US1] Ops: start 24–72h production baseline capture; note window start in `specs/050-performance-cleanup-scaling/research.md`

**Checkpoint**: US1 — operators can measure before/after; MVP-A shippable alone

---

## Phase 4: User Story 2 — Dead packages & deterministic installs (Priority: P1) 🎯 MVP-A

**Goal**: Delete unused training packages; fix energy editable install; strip Alembic/ORM from bot runtime deps

**Independent Test**: Fresh `pip install -r requirements.txt` imports `energy`; `rg training_engine` / training package imports clean in apps; bot starts without alembic/sqlalchemy

### Implementation for User Story 2

- [x] T017 [P] [US2] Delete `packages/training/` after T004 gate; remove any exclusive abandoned tests under `tests/` that only covered that package
- [x] T018 [P] [US2] Delete `packages/training_engine/` after T004 gate; fix docs references if any under `PROJECT_MEMORY.md` / AGENTS only if they claim it is live (ponytail: minimal doc touch)
- [x] T019 [US2] Add `-e packages/energy` to `requirements.txt`; verify `python -c "import energy"`
- [x] T020 [US2] Remove `alembic`, `SQLAlchemy`, `Mako`, `greenlet` from `requirements.txt` after `rg` confirms no imports in `apps/` / `packages/`; keep `sentry-sdk`
- [x] T021 [P] [US2] Ensure `asyncpg` lives in `requirements-ops.txt` (not required for bot runtime) per T007; update any deploy docs that listed it as bot-needed only if such docs exist and user-facing install path is wrong
- [x] T022 [US2] Catalog loaded cogs / app_commands / persistent views / custom_id handlers (script or markdown under `specs/050-performance-cleanup-scaling/contracts/ui-surface-catalog.md`) before any placeholder UI deletion

**Checkpoint**: US2 — clean install surface; safe for hot-path work

---

## Phase 5: User Story 3 — Leaderboard server-side pages (Priority: P1) 🎯 MVP-B

**Goal**: Replace unbounded division fetch and fragile global top-100 pattern with page RPCs + cursors

**Independent Test**: Large division returns ≤10 rows/page; viewer rank + cutoffs correct; global stable on LP ties; second page via cursor; no full-division payload

**Contracts**: [cursor-pagination.md](./contracts/cursor-pagination.md), [round-trip-budgets.md](./contracts/round-trip-budgets.md)

### Tests for User Story 3

- [x] T023 [P] [US3] Add `tests/test_leaderboard_page_budget.py`: page size ≤ requested; cursor round-trip; tie-break ordering helpers (mock or SQL skip-if-no-DB)

### Implementation for User Story 3

- [x] T024 [US3] Author `supabase/migrations/090_performance_read_rpcs.sql` section for `get_division_leaderboard_page` + `get_global_leaderboard_page` (JSON envelope per data-model); GRANT + schema guard entries
- [x] T025 [P] [US3] Extend `supabase/scripts/verify_required_schema.sql` for new leaderboard RPCs
- [x] T026 [US3] Add `scratch/apply_migration_090.py`; apply on dev; run verify
- [x] T027 [US3] Wire `apps/discord_bot/cogs/leaderboard_cog.py` `_division_embed` / global embed to page RPCs via `cursors.py`; remove unbounded `.select` without limit; keep page size 10
- [x] T028 [P] [US3] Update `LeaderboardView` pagination custom_ids in `apps/discord_bot/cogs/leaderboard_cog.py` (or views module) to carry opaque cursors instead of offset page index if required
- [x] T029 [US3] Measured leaderboard indexes in `091_measured_hot_path_indexes.sql` + `092_prefer_division_lb_index.sql` (EXPLAIN snapshots `scratch/explain_snapshots/20260731T142205Z_050_*` / `20260731_after092_*`); not speculative duplicates of `080+`

**Checkpoint**: US3 — leaderboard scale path fixed (highest-value read)

---

## Phase 6: User Story 4 — Transfer Board + marketplace reads (Priority: P1) 🎯 MVP-B

**Goal**: Server-side browse; collapse sell eligibility + marketplace hub to one RPC each

**Independent Test**: Filters discover listings beyond old first-50 window; page ≤25; sell/hub single RT; UI eligibility parity

**Contracts**: [cursor-pagination.md](./contracts/cursor-pagination.md), [round-trip-budgets.md](./contracts/round-trip-budgets.md)

### Tests for User Story 4

- [x] T030 [P] [US4] Add `tests/test_market_browse_server_filter.py`: assert browse helper/RPC contract requires server filters (no “fetch N then filter” path in production code — grep/guard test)

### Implementation for User Story 4

- [x] T031 [US4] Extend `supabase/migrations/090_performance_read_rpcs.sql` (or `090b` forward fix if 090 already applied) with `browse_transfer_market`, `get_market_sell_eligible_cards`, `get_marketplace_hub_state`; GRANT + guards
- [x] T032 [P] [US4] Extend `supabase/scripts/verify_required_schema.sql` for market RPCs
- [x] T033 [US4] Replace `_board_listings` in `apps/discord_bot/views/marketplace_transfer.py` with `browse_transfer_market` RPC; delete Python position/OVR/age/POT filter loop used for correctness
- [x] T034 [US4] Replace 5-gather sell path in `apps/discord_bot/cogs/marketplace_cog.py` `show_sell_menu` with `get_market_sell_eligible_cards`
- [x] T035 [US4] Replace hub gather+count in `apps/discord_bot/cogs/marketplace_cog.py` `show_marketplace_hub` with `get_marketplace_hub_state`
- [x] T036 [US4] Waived after EXPLAIN — `transfer_listings_status_expires_idx` already used; Sort only ~6 active rows (`browse_active_*` snapshots). No market-index migration; `092` used for division index prefer instead

**Checkpoint**: US4 — market browse correct at scale; sell/hub consolidated

---

## Phase 7: User Story 5 — Development hub consolidated reads (Priority: P2)

**Goal**: One read-state RPC for `/development`; skills/mentor without redundant re-fetches; batch remaining config clusters

**Independent Test**: Hub open does not create legendary pending; skills/mentor fewer RTs; pack rarity uses batched config; budgets in contract met

**Contracts**: [round-trip-budgets.md](./contracts/round-trip-budgets.md)

### Tests for User Story 5

- [x] T037 [P] [US5] Add/extend `tests/test_hub_round_trip_budgets.py` with annotated max RT expectations for development hub / marketplace hub / leaderboard page helpers

### Implementation for User Story 5

- [x] T038 [US5] Add `get_development_hub_state` (read-only) + `get_skill_allocation_hub` (+ mentor targets as needed) to performance read migration (`090`/`093_hub_state_rpcs.sql` if split); explicitly exclude ensure/create mutations
- [x] T039 [US5] Wire `apps/discord_bot/cogs/development_cog.py` `show_hub` to hub-state RPC; keep `ensure_pending_legendary` / claims as separate explicit actions
- [x] T040 [US5] Wire `show_skills_menu` / mentor target loading in `apps/discord_bot/cogs/development_cog.py` to consolidated RPCs; remove redundant full-card double fetch where safe
- [x] T041 [P] [US5] Convert `get_pack_rarity_override` in `apps/discord_bot/core/economy_rpc.py` to `get_game_config_many`; grep remaining multi-config clusters on same path under `apps/discord_bot/` and batch them
- [ ] T042 [US5] Optional maintainability (after RPC green): extract internal modules under `apps/discord_bot/features/development/` (`hub.py`, `drills.py`, …) without new slash commands — only if `development_cog.py` still >~2k LOC and Phase 5–6 stable

**Checkpoint**: US5 — progression hub feels like one load; mutations stay explicit

---

## Phase 8: User Story 6 — CacheBackend + shared read tiers (Priority: P2)

**Goal**: Replace ad-hoc dict sprawl with `CacheBackend`; migrate config cache; add guild/standings/first-page/profile-display + single-flight

**Independent Test**: Tier 1–2 hit rate measurable ≥80% in soak; spends still fail closed on live balance; stampede single-flight unit test green

**Contracts**: [cache-policy.md](./contracts/cache-policy.md)

### Tests for User Story 6

- [x] T043 [P] [US6] Add `tests/test_cache_backend.py`: TTL expiry, `delete_prefix`, single-flight `get_or_set` (one factory call under concurrent awaiters)

### Implementation for User Story 6

- [x] T044 [US6] Create `apps/discord_bot/core/cache/backend.py` Protocol + `apps/discord_bot/core/cache/memory.py` with single-flight
- [x] T045 [US6] Migrate `apps/discord_bot/core/config_cache.py` to use `CacheBackend` (preserve key scheme `cfg:…`)
- [x] T046 [P] [US6] Add guild config cache helpers (TTL 5–15m) used by league/admin hot reads — wire invalidate on admin guild config writes
- [x] T047 [P] [US6] Add standings / leaderboard-first-page short TTL cache (15–60s) with invalidate hooks after settle/reset paths (grep call sites in `apps/discord_bot/`)
- [x] T048 [US6] Add short profile-display cache (15–30s) with invalidate after economy/match/login/promo mutations — **never** authorize spends from cache
- [x] T049 [US6] Expose cache stats via `perf_signals` / admin Performance panel

**Checkpoint**: US6 — disposable cache accelerates shared reads; authority stays in DB

---

## Phase 9: User Story 7 — Mature feature flags & Match V2 path (Priority: P3)

**Goal**: Inventory → soak → make permanent; remove obsolete kill switches and parallel league modes — **separate deploys from US3–US5**

**Independent Test**: Flag inventory complete; after soak, Mentor has no env gate; V3 defaults; no new V2 runs; league has one authoritative path per responsibility

### Implementation for User Story 7

- [x] T050 [US7] Produce soak checklist in `specs/050-performance-cleanup-scaling/contracts/flag-maturity-checklist.md` (introduced_at, remove_after, owner, rollback) for Mentor + three V3 keys + league flags
- [ ] T051 [US7] Ops: staged V3 soak + metrics — tooling live (`ops_match_v3_rollout.py soak-report` / stages); flags already Stage 3 on current DB; window started 2026-07-31 in `ops-v3-soak-log.md`. Complete human smoke + exit criteria before T052 (do **not** flip defaults / delete V2 yet)
- [ ] T052 [US7] After soak: change `resolve_engine_version` defaults in `apps/discord_bot/core/match_runs.py` to prefer V3 when config row absent; keep emergency rollback keys temporarily
- [ ] T053 [US7] Stop creating new V2 runs; retain V2 recovery readability until drain confirmed
- [ ] T054 [US7] After no active/recoverable V2 runs: remove `packages/match_engine/match_engine/v2_simulator.py` and V2 branches in `battle_cog.py`, `league_cog.py`, `match_runs.py`, `match_recovery.py` — **not** shared models/formations
- [ ] T055 [US7] Remove `MENTOR_TRANSFUSION_ENABLED` / `_mentor_enabled()` from `apps/discord_bot/cogs/development_cog.py` and `.env.example` after production stability confirmed
- [ ] T056 [US7] Audit `league_dynamics_enabled` / `league_automation_enabled` vs `league_state_machine_job` / `league_lifecycle_wake_job` / `auto_sim_expired_fixtures_job` in `apps/discord_bot/main.py` + `league_automation.py`; consolidate or delete obsolete parallel mode — keep required expired-fixture worker if still authoritative

**Checkpoint**: US7 — fewer permanent boolean branches; V2 retirement controlled

---

## Phase 10: User Story 8 — Durable jobs & multi-instance readiness (Priority: P3)

**Goal**: Generalize claim/outbox; move safe work off interaction path; document horizontal scale gates

**Independent Test**: Kill process mid-job → work resumes or fails safely; two workers cannot double-apply claimed job; admin shows queue depth

**Contracts**: [job-idempotency.md](./contracts/job-idempotency.md)

### Implementation for User Story 8

- [ ] T057 [US8] Harden/generalize claim helpers in `apps/discord_bot/core/job_claims.py` + `apps/discord_bot/core/league_outbox.py`; add `supabase/migrations/094_job_outbox_hardening.sql` only if schema gaps proven
- [ ] T058 [US8] Move Discord notification fanout / non-critical analytics off interaction path onto claimed jobs (identify call sites in `apps/discord_bot/`); do **not** defer core match settlement
- [ ] T059 [US8] Chunk season-end / large maintenance batches (50–200 clubs per claim) where applicable under `apps/discord_bot/core/` / scheduler jobs
- [ ] T060 [US8] Ensure every scheduled job in `apps/discord_bot/main.py` is claim-wrapped **or** gated by `RUN_SCHEDULER=1` documented in quickstart
- [ ] T061 [P] [US8] Expose job queue depth / oldest pending on admin Performance panel
- [ ] T062 [US8] Write multi-instance + Discord sharding runbook section in `specs/050-performance-cleanup-scaling/quickstart.md` (AutoShardedBot plan; Redis optional behind same cache API — no Redis required yet)
- [ ] T063 [US8] Process-local concurrency semaphore for non-critical read fanout in `apps/discord_bot/core/db_concurrency.py` (limit from load tests; default conservative)

**Checkpoint**: US8 — restart-safe background work; horizontal checklist documented

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Indexes from evidence, load suite, UI dead-code sweep, docs, regression budgets

- [x] T064 [P] Remaining measured index (`idx_league_fixtures_season_played`) shipped in `091_measured_hot_path_indexes.sql` (`093` is hub-state RPCs). Before/after in query-plan-gate + research R8
- [ ] T065 [P] Implement `scripts/load/leaderboard_read.py`, `marketplace_browse.py`, `development_hub.py`, `profile_read.py`, `mixed_workload.py` against staging RPCs (never production Discord)
- [ ] T066 Run mixed load stages (10→…→stop at knee); record saturation notes in `specs/050-performance-cleanup-scaling/research.md`
- [ ] T067 Using T022 catalog, delete confirmed-dead placeholder Views/modals/“Coming Soon” with no planned use under `apps/discord_bot/views/` / `cogs/` / `embeds/` — preserve persistent custom_ids still referenced by old messages
- [ ] T068 [P] Grep CI/structural: no OFFSET primary pagination on leaderboards/market/history hot paths; no unbounded division select; pack rarity not dual `get_game_config`
- [ ] T069 Update `change_log.md` only if player-visible latency/behavior notes are warranted; update `specs/050-performance-cleanup-scaling/checklists/requirements.md` Notes with tasks completion pointer
- [ ] T070 Run `specs/050-performance-cleanup-scaling/quickstart.md` Phase 1–2 validation gates end-to-end on staging
- [ ] T071 Fill after-columns in `contracts/round-trip-budgets.md`; confirm SC-002 ≥50% RT cut on Division LB + Transfer Board + ≥1 hub-state path before calling epic performance-complete

**Checkpoint**: Polish done — epic success criteria measurable

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: immediate
- **Foundational (Phase 2)**: after Setup — blocks US3–US6 hard; soft-blocks US1 metrics identity
- **US1 + US2 (P1)**: after Setup; parallelizable with each other and with late Foundational
- **US3 then US4 (P1)**: after Foundational + prefer US1 baseline started; US4 may follow US3 in same migration wave but separate cog files allow parallel after 090 authored
- **US5 (P2)**: after US4 preferred (shared migration patterns); must not mix with US7 deploy
- **US6 (P2)**: after US3–US5 query shaping (do not cache bad full-table reads)
- **US7 / US8 (P3)**: after US3–US5 stable in production; **never** same deploy as US3–US5 RPC cutover
- **Polish**: after chosen stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Setup (+ T005 ideal) | MVP-A |
| US2 | Setup T004 | MVP-A; parallel with US1 |
| US3 | Foundational cursors + prefer US1 baseline | MVP-B |
| US4 | Foundational + 090 pattern (US3) | MVP-B |
| US5 | US4 patterns | Read-only hub RPC |
| US6 | US3–US5 | Cache after shape |
| US7 | Production soak; not US3 deploy | Separate release |
| US8 | Claim patterns; after US6 optional | Scale gate |

### Parallel Opportunities

- T001–T004 Setup `[P]` where marked
- T006–T008 Foundational `[P]`
- T017–T018 package deletes `[P]` after T004
- T023 / T030 / T037 / T043 tests `[P]` before/with their stories
- US1 ∥ US2 after Setup
- US3 cog wire ∥ US4 view wire after shared migration applied
- T046 ∥ T047 cache tiers
- T064 ∥ T065 polish scripts/indexes

---

## Parallel Example: MVP-B (Leaderboard + Market)

```text
# After 090 applied on staging:
Task: "Wire leaderboard_cog to page RPCs"
Task: "Replace marketplace_transfer _board_listings with browse RPC"
Task: "tests/test_leaderboard_page_budget.py"
Task: "tests/test_market_browse_server_filter.py"
```

---

## Parallel Example: US1 Observability

```text
Task: "Extend perf_signals.py buckets"
Task: "Add sentry_setup.py"
Task: "Extend baseline_hub_roundtrips.py"
```

---

## Implementation Strategy

### MVP First (MVP-A → MVP-B)

1. Phase 1 Setup + Phase 2 Foundational  
2. **US1 + US2** → ship measurement + clean deps (**MVP-A**)  
3. **STOP**: capture baseline window  
4. **US3 + US4** → leaderboard pages + market browse/sell/hub (**MVP-B**)  
5. **STOP and VALIDATE**: RT budgets + quickstart Phase 2 gates  
6. Continue US5 → US6 → (separate) US7/US8 → Polish  

### Incremental Delivery

1. Cleanup + metrics (no gameplay risk)  
2. Additive RPCs + new bot (old bot still works)  
3. Delete old Python paths after measure  
4. Cache only after queries shaped  
5. Flag/V2 work on its own release train  
6. Outbox/multi-instance when single-instance gains plateau  

### Suggested first implementation sprint

Per plan §60 / quickstart: **T010–T022** (US1–US2) → **T023–T036** (US3–US4). Do not bump HTTP pool. Do not start US7 V2 deletion in the same PR.

---

## Notes

- [P] = different files, no incomplete deps  
- Additive SQL before deleting PostgREST paths  
- Development hub read ≠ legendary ensure  
- Free-tier: prefer fewer rows/RTs over more connections  
- `049` DM ops remain out of scope  
- Commit after each task group when implementing; do not combine US7 with US3–US5

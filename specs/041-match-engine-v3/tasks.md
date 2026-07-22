# Tasks: Match Engine V3 — Deterministic Tactical Engine

**Input**: Design documents from `/specs/041-match-engine-v3/`

**Prerequisites**: plan.md, spec.md (clarifications Q1–Q4), research.md, data-model.md, contracts/, quickstart.md

**Tests**: **Required** by FR-017 / SC-001–SC-011 (Golden Corpus + digests). Write failing tests before or with implementation for Phase 0 gates.

**Organization**: By user story. **MVP = Phase 0 architectural parity** (US1–US4 foundation). US5–US8 are post–Phase 0 waves unless noted as Phase 0 stubs.

**Clarification locks**: Phase 0 = no intentional gameplay change; immediate Decision apply; three digests; possession-boundary flush; fixed DecisionWindows enforce in Wave 1 only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no incomplete dependency)
- **[Story]**: [US1]…[US8] for story phases only

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package layout + docs sync so implementation has a home

- [x] T001 Create `packages/match_engine/match_engine/v3/` package tree (`__init__.py`, `context.py`, `events.py`, `engine.py`, `phases.py`, `decisions.py`, `possession.py`, `digests.py`, `projectors.py`, `tactics.py`, `rng.py`) per `specs/041-match-engine-v3/plan.md`
- [x] T002 [P] Create `packages/match_engine/match_engine/contracts/` with Protocol stubs (`simulation.py`, `events.py`, `decision.py`, `projector.py`) per plan + clarify review
- [x] T003 [P] Create `packages/match_engine/match_engine/calibration/` package (`__init__.py`, `golden/`, `README.md`) for Golden Corpus + offline harnesses
- [x] T004 [P] Sync stale contracts to clarifications: update `specs/041-match-engine-v3/contracts/event-store.md` (possession-boundary flush), `event-model.md` (categories + digests), `ai-decision.md` (BotBrain→Policy), `simulation-api.md` (DecisionInbox immediate apply Phase 0)
- [x] T005 Export v3 public API surface from `packages/match_engine/__init__.py` / `match_engine/__init__.py` without breaking v2 `stream_match` imports

**Checkpoint**: Package skeleton importable; v2 still loads

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models, digests, migration, flags — blocks all story work

**⚠️ CRITICAL**: No user-story adapter wiring until this phase completes

- [x] T006 Implement `MatchEvent` envelope + categories (Sporting/Decision/Administrative/Projection) in `packages/match_engine/match_engine/v3/events.py`
- [x] T007 [P] Implement immutable `MatchContext`, `Possession`, `DecisionContext`, `StepResult`, `ReplayMeta` in `packages/match_engine/match_engine/v3/context.py` + `possession.py`
- [x] T008 [P] Implement seeded RNG helper (no global random) in `packages/match_engine/match_engine/v3/rng.py`
- [x] T009 Implement `DecisionInbox` + `DecisionIntent` (validate → collapse → **immediate** apply + window metadata) in `packages/match_engine/match_engine/v3/decisions.py`
- [x] T010 Implement Sporting / Deterministic Replay / Settlement digest recipes in `packages/match_engine/match_engine/v3/digests.py` (FR-021)
- [x] T011 [P] Implement box-score + Replay projector **stubs** in `packages/match_engine/match_engine/v3/projectors.py`
- [x] T012 [P] Implement thin `BotBrain` + `DefaultPolicy` protocols in `packages/match_engine/match_engine/v3/` (and `contracts/decision.py`) — DefaultPolicy only
- [x] T013 Author migration `supabase/migrations/083_match_engine_v3_events.sql`: `match_events` table, `match_runs.engine_version`, `simulation_schema_version`, `event_schema_version`, `events_flushed_thru`, RLS, schema guards
- [x] T014 [P] Extend `supabase/scripts/verify_required_schema.sql` for new table/columns/policies
- [x] T015 [P] Add `scratch/apply_migration_083.py` following existing apply-script pattern
- [x] T016 Add game_config / flag keys for dual-run (`match_engine_v3_bot|league|friendly`) documented in `specs/041-match-engine-v3/contracts/migration-dual-run.md` and mirrored in ops notes / economy config defaults if required
- [x] T017 Extend `apps/discord_bot/core/match_runs.py` to set immutable `engine_version` + `simulation_schema_version` on create
- [x] T018 Add `apps/discord_bot/core/match_events_store.py` for batched append on possession boundaries + forced HT/FT/injury/completing flushes

**Checkpoint**: Foundation ready — digests + schema + inbox exist; engine body still next

---

## Phase 3: User Story 1 — Same match, same outcome forever (P1) 🎯 MVP

**Goal**: Deterministic step engine + digests; v3↔v3 identical replay

**Independent Test**: Same seed+squads+decisions → identical Deterministic Replay Digest twice; SC-001

### Tests for User Story 1

- [x] T019 [P] [US1] Add `tests/test_nss_v3_determinism.py` (failing until engine ready) — digest identity across two runs
- [x] T020 [P] [US1] Add property tests in `tests/test_nss_v3_properties.py` — seq monotonic, score = GOAL count, FT terminal

### Implementation for User Story 1

- [x] T021 [US1] Port NSS Markov phases into `packages/match_engine/match_engine/v3/phases.py` (bases, /55, 5% floor, momentum, stagnation — parity intent)
- [x] T022 [US1] Implement `SimulationEngine.initial_context` / `step` / `run_to_completion` in `packages/match_engine/match_engine/v3/engine.py`
- [x] T023 [US1] Emit categorized `MatchEvent`s from phase transitions (GOAL/SAVE/MISS/CHANCE/etc.) without Projection-as-input
- [x] T024 [US1] Wire Possession lifecycle start/end around phase graph in `packages/match_engine/match_engine/v3/possession.py` + engine
- [x] T025 [US1] Ensure no wall-clock / global RNG in sporting path (grep + tests)
- [x] T026 [US1] Make T019–T020 pass

**Checkpoint**: Silent `run_to_completion` is deterministic offline

---

## Phase 4: User Story 2 — Simulation not tied to Discord pacing (P1)

**Goal**: Live/silent/recovery adapters share the same engine

**Independent Test**: Live-paced consumer vs silent collector → same Sporting + Replay digests

### Tests for User Story 2

- [x] T027 [P] [US2] Add `tests/test_nss_v3_adapter_parity.py` — async generator wrapper vs `run_to_completion` digest equality

### Implementation for User Story 2

- [x] T028 [US2] Add `stream_match_v3` async adapter (yield Discord-compat dicts + sleep-agnostic) wrapping `step` in `packages/match_engine/match_engine/v3/` or facade
- [x] T029 [US2] Replace silent path `collect_match_events` call sites for v3-pinned runs in `packages/match_engine/match_engine/v2_simulator.py` bridge or new `collect_match_events_v3`
- [x] T030 [US2] Update `apps/discord_bot/cogs/battle_cog.py` bot live loop to consume v3 when `engine_version=nss_v3` (keep v2 path for pin)
- [x] T031 [US2] Update `apps/discord_bot/core/match_recovery.py` to branch on `engine_version` (v2 legacy vs v3 `run_to_completion`)
- [x] T032 [US2] Make T027 pass

**Checkpoint**: Discord is a consumer only for v3 runs

---

## Phase 5: User Story 3 — Event stream is source of truth (P1)

**Goal**: Projectors derive stats; settlement attribution from events

**Independent Test**: `project_box_score(events)` agrees with GOAL/POSSESSION/SHOT semantics; rewards key_events from events

### Tests for User Story 3

- [x] T033 [P] [US3] Add `tests/test_nss_v3_projectors.py` — box score from events; Projection excluded from Sporting Digest
- [x] T034 [P] [US3] Add `tests/test_nss_v3_digests.py` — Sporting vs Replay vs Settlement recipe membership

### Implementation for User Story 3

- [x] T035 [US3] Complete box-score projector (possession/shots/goals/MOTM) in `packages/match_engine/match_engine/v3/projectors.py`
- [x] T036 [US3] Build `key_events` / XP attribution inputs from canonical events in `apps/discord_bot/core/match_xp.py` callers / battle finalize path (no ticker-only memory as SoT)
- [x] T037 [US3] Flush events via `match_events_store` on possession boundaries in live bot/league adapters
- [x] T038 [US3] Make T033–T034 pass; enforce SC-010 (Projection not in replay inputs)

**Checkpoint**: Stats/commentary/rewards read from events

---

## Phase 6: User Story 4 — No integrity / match-type regression (P1)

**Goal**: Dual-run + settle-once + friendly sandbox unchanged

**Independent Test**: Integrity matrix + dual-run pin tests green

### Tests for User Story 4

- [x] T039 [P] [US4] Add `tests/test_nss_v3_dual_run_pin.py` — in-flight v2 stays v2; flag only affects new runs
- [x] T040 [P] [US4] Extend `tests/test_match_integrity_recovery.py` / `tests/test_match_reward_wiring.py` for v3 adapter settle-once + friendly no economy
- [x] T041 [P] [US4] Add SQL guard tests pattern in `tests/test_match_integrity_sql_guards.py` (or sibling) for migration 083 objects

### Implementation for User Story 4

- [x] T042 [US4] Wire feature flags into `create_ephemeral_run` / `create_league_run` in `apps/discord_bot/core/match_runs.py`
- [x] T043 [US4] Ensure friendly path remains sandbox (no `match_events` by default; no reward RPCs) in `apps/discord_bot/cogs/battle_cog.py`
- [x] T044 [US4] League auto-sim / lifecycle silent path uses v3 when flagged in `apps/discord_bot/core/league_lifecycle_engine.py` / `league_automation.py`
- [x] T045 [US4] Apply migration 083 on staging via scratch script; run `verify_required_schema`
- [x] T046 [US4] Make T039–T041 pass

**Checkpoint**: US-42.4 guarantees hold under dual-run

---

## Phase 7: Golden Corpus & Phase 0 exit gates (cross-cutting P1)

**Goal**: 50–100 fixtures; exact_parity / stats_parity; unlock Wave 1

**Independent Test**: Corpus CI job green; SC-008/009/011

- [x] T047 Capture NSS v2 baselines into `packages/match_engine/match_engine/calibration/golden/` (inputs + Sporting/Settlement digests) for ≥50 fixtures spanning even/underdog/morale/formation/injury/bot/league/friendly/recovery
- [x] T048 [P] Implement corpus runner in `packages/match_engine/match_engine/calibration/run_corpus.py` (or `tests/test_nss_v3_golden_corpus.py`)
- [x] T049 Tag fixtures `exact_parity` (default) vs `stats_parity` (+ architectural reason metadata); enforce SC-011
- [x] T050 [P] Add performance budget test `tests/test_nss_v3_perf.py` (CPU &lt;50ms, memory &lt;5MB guidance)
- [x] T051 Re-run / extend `tests/test_nss_win_rates.py` against v3 Balanced for Phase 0 parity bands
- [x] T052 Document Phase 0 exit checklist results in `specs/041-match-engine-v3/quickstart.md` (checkboxes)
- [x] T053 Update `change_log.md` only when staging flag enable is planned (player-facing transparency); otherwise note “pending enable”

**Checkpoint**: FR-018 Phase 0 acceptance — **STOP before Wave 1 gameplay changes**

---

## Phase 8: User Story 7 — DecisionInbox live wiring (P2, Phase 0 stub complete → Wave 1 enforce)

**Goal**: Touchline → DecisionInbox events (immediate apply Phase 0); Wave 1 window enforcement later

**Independent Test**: Decision events replay; Phase 0 timing matches v2 immediacy

### Tests for User Story 7

- [x] T054 [P] [US7] Add `tests/test_nss_v3_decisions.py` — collapse/spam, immediate apply Phase 0, ignore post-FT
- [x] T055 [P] [US7] Add Wave 1-marked tests (skipped until schema bump) for fixed windows 15/30/45/60/75/85

### Implementation for User Story 7

- [x] T056 [US7] Refactor `TouchlineView` in `apps/discord_bot/cogs/battle_cog.py` to push `DecisionIntent` into inbox (no direct MatchState mutation for v3)
- [x] T057 [US7] Persist Decision-category events with window metadata during live v3 matches
- [x] T058 [US7] Recovery replays Decision events with schema-pinned apply semantics in `apps/discord_bot/core/match_recovery.py`
- [x] T059 [US7] **Wave 1 only**: enforce fixed DecisionWindows; bump `simulation_schema_version`; regenerate Golden Corpus; update `change_log.md`

**Checkpoint**: Phase 0 decisions are evented + immediate; Wave 1 gated

---

## Phase 9: User Story 5 — Explainability (P2, post–Phase 0 rich UI)

**Goal**: Post-match explanation from Sporting Digest / events

**Independent Test**: Same stream → same explanation turning points

### Tests for User Story 5

- [x] T060 [P] [US5] Add `tests/test_nss_v3_explainability.py` — deterministic turning-point selection

### Implementation for User Story 5

- [x] T061 [US5] Implement explainability projector in `packages/match_engine/match_engine/v3/projectors.py`
- [x] T062 [US5] Surface explanation on bot/league finalize embeds in `apps/discord_bot/cogs/battle_cog.py` handlers
- [x] T063 [US5] Make T060 pass (SC-006 playtest is manual later)

**Checkpoint**: Managers see stream-grounded “why”

---

## Phase 10: User Story 6 — Tactical transition styles (P2, Wave 2)

**Goal**: Possession/Counter/Long Ball/High Press alter transitions — not goal% padding

**Independent Test**: SC-005 distinguishability; schema bump

### Tests for User Story 6

- [x] T064 [P] [US6] Add `tests/test_nss_v3_tactics_distinguishability.py`
- [x] T065 [P] [US6] Win-rate band re-approval suite after style enable

### Implementation for User Story 6

- [x] T066 [US6] Implement `TransitionProfile` data in `packages/match_engine/match_engine/v3/tactics.py`
- [x] T067 [US6] Apply profiles in phase transition weights/timings (not primary goal chance inflation) in `phases.py`
- [x] T068 [US6] Bump `simulation_schema_version`; regenerate corpus; player-facing changelog
- [x] T069 [US6] Make T064–T065 pass

**Checkpoint**: Styles distinguishable; digests versioned

---

## Phase 11: User Story 8 — BotBrain → Policy (P3, thin in Phase 0)

**Goal**: AI never mutates context; DefaultPolicy Phase 0; richer policies later

**Independent Test**: Swap Policy without engine API change

### Tests for User Story 8

- [x] T070 [P] [US8] Add `tests/test_nss_v3_bot_policy.py` — DefaultPolicy deterministic; no context mutation

### Implementation for User Story 8

- [x] T071 [US8] Call `BotBrain.propose` at decision barriers / injury auto path from engine or adapter
- [x] T072 [US8] **Wave 3 only**: add Aggressive/Defensive Policy modules under `packages/match_engine/match_engine/v3/policies/` without changing `SimulationEngine` API
- [x] T073 [US8] Make T070 pass; CI grep that battle_cog does not import Dixon-Coles

**Checkpoint**: AI is an event producer only

---

## Phase 12: Polish & Cross-Cutting

**Purpose**: Docs, cleanup, calibration formalization

- [x] T074 [P] Move/compare Dixon-Coles harness entrypoint under `packages/match_engine/match_engine/calibration/` (scripts may thin-wrap); ensure no Discord import
- [x] T075 [P] Update `.specify/specs/v1.0.0/plan.md` NSS section to point at v3 dual-run + digests (reconcile SDD)
- [x] T076 Grep cleanup: no accidental v3 sporting use of `random.` global; no `time.time` in engine
- [x] T077 Run full `specs/041-match-engine-v3/quickstart.md` validation suite; fix failures
- [x] T078 [P] Update `specs/041-match-engine-v3/plan.md` Next Command → implement; mark Wave 0 tasks done when exited
- [x] T079 Optional retention sweeper design note only (YAGNI code unless ops requests) in `contracts/event-store.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup** → **Phase 2 Foundational** (blocks all stories)
- **US1 → US2 → US3 → US4** sequential recommended (shared engine/adapters)
- **Golden Corpus (Phase 7)** after US1–US4; **blocks Wave 1+**
- **US7 Phase 0 wiring** can overlap late US2/US3; **US7 Wave 1 enforce** after Phase 7
- **US5 / US6 / US8 richer** after Phase 7 (US8 thin already in Phase 2)

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP core |
| US2 | US1 | Adapters |
| US3 | US1 | Projectors/events store |
| US4 | US2–US3 | Flags + integrity |
| Corpus | US1–US4 | Phase 0 exit |
| US7 | US1 + inbox (T009) | Immediate now; windows Wave 1 |
| US5 | US3 projectors | Post–Phase 0 rich UI |
| US6 | Corpus exit | Schema bump |
| US8 thin | Phase 2 | Already stubbed; wire in US2/US7 |
| US8 rich | Corpus exit | Wave 3 |

### Parallel Opportunities

- T002/T003/T004 after T001
- T007/T008/T011/T012/T014/T015 after T006 started
- T019/T020 before T021 finishes (TDD)
- T033/T034, T039/T040/T041 in parallel once engine exists
- US5/US6/US8 rich after Phase 7 can be parallelized by different owners

---

## Parallel Example: User Story 1

```text
# Tests first (fail):
T019 tests/test_nss_v3_determinism.py
T020 tests/test_nss_v3_properties.py

# Then engine port:
T021 phases.py
T022 engine.py
T023–T025 events + possession + RNG hygiene
T026 green tests
```

---

## Implementation Strategy

### MVP (Phase 0 / US1–US4 + Corpus)

1. Phase 1 Setup  
2. Phase 2 Foundational  
3. US1 determinism → US2 adapters → US3 SoT → US4 integrity  
4. Golden Corpus + exit gates  
5. **STOP** — no Wave 1 window enforcement / tactics / rich explain UI until FR-018 signed off  

### Incremental delivery after Phase 0

1. US7 live DecisionInbox (immediate) if not fully done  
2. Wave 1: window enforcement + changelog + corpus regen  
3. US5 explainability UI  
4. US6 tactical styles  
5. US8 richer policies  

### Suggested first merge slice

**T001–T026 + T019/T020 green** = offline deterministic engine with digests (no Discord flag yet).

---

## Notes

- Do **not** merge Dixon-Coles into live paths (T073/T074).
- Do **not** intentionally change gameplay in Phase 0 (clarification Q1/Q4).
- Migration number **083** — renumber if another migration lands first.
- Every task includes a path so an implementer can execute without re-deriving architecture.
- Prefer smallest diffs; reuse `v2_simulator` logic by port, not by copy-paste drift.

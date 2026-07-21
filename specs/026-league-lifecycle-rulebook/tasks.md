# Tasks: League Rulebook and Autonomous Lifecycle Engine V1

**Input**: Design documents from `/specs/026-league-lifecycle-rulebook/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md  
**Depends on**: Existing guild league (007+), Dynamics/automation surfaces (020/021) available for grandfathering — do not rewrite living seasons

**Tests**: Include pure unit tests listed in plan.md (schedule DST, double forfeit, assistant priority, idempotency, pause/resume, cutover). No full Discord integration suite required in V1 tasks.

**Locked decisions** (research.md / clarifications):
- Q1: Guild IANA timezone + local resolution hour; freeze + precompute UTC; DST gap → first valid after; overlap → earlier offset
- Q2: Double forfeit 0–0, 0 pts, MP+1/L+1; not draw/clean sheet/unbeaten/appearance/promo-eligible
- Q3: Feature-flagged exclusive per-guild cutover; 021 → thin wake-up; rollback = stop new V1 seasons
- Migration: `070_league_lifecycle_v1.sql`
- No new player slash commands; competitive rules never live in the scheduler job body

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema / engine work

- [x] T001 Grep `league_state_machine_job`, `start_dynamics_season_from_registration`, `auto_sim_expired_fixtures`, `update_current_matchday`, `distribute_season_prizes`, `pacing_mode`, `LeagueManagementView`, `play_league_match` callers; confirm touch list matches `specs/026-league-lifecycle-rulebook/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_070.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)
- [x] T003 [P] Create stub module files listed in plan (empty `__doc__` + `from __future__ import annotations` only): `packages/leagues/leagues/lifecycle_states.py`, `schedule.py`, `assistant_lineup.py`, `forfeit_rules.py`, `operation_keys.py`; `apps/discord_bot/core/league_lifecycle_engine.py`, `league_recovery.py`, `league_outbox.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, pure rulebook primitives, cutover flags, operation keys — **MUST complete before any user-story engine wiring**

**⚠️ CRITICAL**: No scheduler wake-up, no V1 season create, no fixture settle path until this phase is done and schema verify passes

- [x] T004 [P] Implement status enums + allowed transition map in `packages/leagues/leagues/lifecycle_states.py` per `contracts/lifecycle-transitions.md` and `data-model.md` (season / matchday / fixture statuses)
- [x] T005 [P] Implement idempotency key builders in `packages/leagues/leagues/operation_keys.py` per normative keys in `contracts/lifecycle-transitions.md`
- [x] T006 [P] Implement IANA schedule generator in `packages/leagues/leagues/schedule.py` per `contracts/matchday-schedule.md` (`zoneinfo`; DST gap/overlap rules; return UTC `window_start`/`window_end` for matchdays 1–14)
- [x] T007 [P] Implement forfeit / double-forfeit standings deltas in `packages/leagues/leagues/forfeit_rules.py` per `contracts/fixture-resolution.md` (3–0 and 0–0 double_forfeit with MP+1/L+1/0 pts)
- [x] T008 [P] Implement assistant lineup priority helpers in `packages/leagues/leagues/assistant_lineup.py` per `contracts/fixture-resolution.md` (submitted → saved → repair → emergency → forfeit; no Discord imports)
- [x] T009 [P] Extend `packages/leagues/leagues/seasonal_divisions.py` for human-first promo/releg + reduce-movement per `contracts/promotion-relegation.md` (keep weekly `calculator.py` untouched)
- [x] T010 Extend `packages/leagues/leagues/standings.py` aggregation to honor `result_type=double_forfeit` (loss, 0 pts, 0 GF/GA; exclude from clean-sheet / unbeaten / promo-eligibility helpers as needed)
- [x] T011 Export new helpers from `packages/leagues/leagues/__init__.py`
- [x] T012 [P] Add `tests/test_league_schedule_windows.py` covering Asia/Kathmandu fixed offset + America/New_York spring gap + fall overlap per research D2
- [x] T013 [P] Add `tests/test_double_forfeit_standings.py` asserting MP/W/D/L/GF/GA/GD/Pts deltas and non-draw / non-promo-eligible flags
- [x] T014 [P] Add `tests/test_assistant_lineup_priority.py` for priority order and repair-without-random-tactics invariants
- [x] T015 Author `supabase/migrations/070_league_lifecycle_v1.sql` per `data-model.md`: guild_config TZ/hour/cutover columns; expand `league_seasons` status + ruleset/engine/snapshot/timezone/phase fields; `pacing_mode` include `lifecycle_v1`; new tables `league_registrations`, `league_divisions`, `league_matchdays`, `league_final_standings`, `league_transition_journal`, `league_operation_runs`, `league_outbox`; alter `league_members` / `league_participants` / `league_fixtures`; RLS + policies; seed `game_config` keys; helper `league_lifecycle_v1_enabled()`; schema guard block
- [x] T016 Extend `supabase/scripts/verify_required_schema.sql` for 070 tables/columns/functions/policies (correct `split_part` for functions and `policy:` entries)
- [x] T017 Apply migration via `scratch/apply_migration_070.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green
- [x] T018 [P] Add cutover helpers in `apps/discord_bot/core/economy_rpc.py`: `league_lifecycle_v1_enabled(db)`, `guild_lifecycle_v1_effective(db, guild_id)` per `contracts/cutover-and-rollback.md`
- [x] T019 [P] Add `tests/test_cutover_grandfathering.py` for effective-flag truth table + “no V1 start while non-V1 open” pure predicate (packages or thin wrapper under test)

**Checkpoint**: Schema verified; `pytest tests/test_league_schedule_windows.py tests/test_double_forfeit_standings.py tests/test_assistant_lineup_priority.py tests/test_cutover_grandfathering.py -q` green; no scheduler changes yet

---

## Phase 3: User Story 1 — Predictable autonomous season cycle (Priority: P1) 🎯 MVP

**Goal**: 21-day cycle transitions (registration → prepare → activate → matchday advance → settle → offseason → next registration) for cutover guilds without admin Start on the happy path

**Independent Test**: With cutover on and TZ/hour set, open registration → ≥4 humans → prepare seats 8-club RR → 14 matchday windows stored → after matchdays complete, settlement + offseason → next registration; no admin Start required

### Implementation for User Story 1

- [x] T020 [US1] Implement operation-run acquire/complete helpers (insert `league_operation_runs` by `operation_key`, succeed/fail) used by the engine in `apps/discord_bot/core/league_lifecycle_engine.py`
- [x] T021 [US1] Implement transition journal writer to `league_transition_journal` in `apps/discord_bot/core/league_lifecycle_engine.py`
- [x] T022 [US1] Implement `process_due_transitions(bot, db, now)` skeleton in `apps/discord_bot/core/league_lifecycle_engine.py` that only processes `ruleset_version` / `pacing_mode=lifecycle_v1` seasons (skip grandfather Dynamics/legacy)
- [x] T023 [US1] Implement registration open/lock/cancel-under-min transitions in `apps/discord_bot/core/league_lifecycle_engine.py` per FR-001/FR-013–015 and `contracts/lifecycle-transitions.md` (create `league_registrations`; set phase deadlines; cancelled ≠ completed)
- [x] T024 [US1] Implement preparation transition: charge deposits via existing `charge_league_entry_fees` (or V1-aware wrapper), create `league_divisions`, seat participants, generate fixtures via `generate_round_robin_fixtures`, assign windows via `packages/leagues` schedule helper, insert `league_matchdays`, freeze TZ/hour/ruleset_snapshot on season — in `apps/discord_bot/core/league_lifecycle_engine.py` (extract shared pieces from `league_automation.start_dynamics_season_from_registration` rather than forking)
- [x] T025 [US1] Implement activate → open matchdays by `window_start` / lock by `window_end` matchday status updates in `apps/discord_bot/core/league_lifecycle_engine.py`
- [x] T026 [US1] Implement season settling → completed path calling prize distribution once (`distribute_season_prizes` or V1 successor), write `league_final_standings`, schedule offseason → next registration in `apps/discord_bot/core/league_lifecycle_engine.py`
- [x] T027 [US1] Enqueue presentation events to `league_outbox` (registration open, schedule release, phase changes) from engine transitions — **do not** send Discord from inside settle transactions — in `apps/discord_bot/core/league_lifecycle_engine.py`
- [x] T028 [US1] Implement outbox publisher in `apps/discord_bot/core/league_outbox.py` that posts via existing `league_announce.py` / `league_journal.py` helpers and marks `published_at` (swallow send errors; never roll back sport)
- [x] T029 [P] [US1] Add read-only `scratch/smoke_league_lifecycle_v1.py` printing effective cutover, sample schedule windows for a TZ/hour, and open V1 seasons

**Checkpoint**: US1 cycle demoable on pilot DB/smoke; Dynamics seasons untouched

---

## Phase 4: User Story 2 — Asynchronous matchday + assistant manager (Priority: P1)

**Goal**: Fixtures resolve at deadline via assistant lineup priority; 3–0 / double_forfeit rules; infra failures retryable; early play has no first-click advantage

**Independent Test**: Valid saved XI left unplayed past `window_end` auto-resolves; both illegal → double_forfeit stats; match-engine failure leaves `failed_retryable` without forfeit

### Implementation for User Story 2

- [x] T030 [US2] Implement fixture resolve/settle pipeline in `apps/discord_bot/core/league_lifecycle_engine.py` per `contracts/fixture-resolution.md` (lease op key, club locks, lineup priority via `assistant_lineup`, seed persistence)
- [x] T031 [US2] Wire automatic resolution to existing match simulation path in `apps/discord_bot/cogs/battle_cog.py` / shared runner so deadline sims reuse NSS engine with stored seed (no random re-roll on recovery)
- [x] T032 [US2] Apply forfeit and double_forfeit terminal writes on `league_fixtures` (`result_type`, scores, `is_played`, `resolved_by`) using `forfeit_rules.py` deltas in the settle path
- [x] T033 [US2] Ensure early manual `play_league_match` in `apps/discord_bot/cogs/league_cog.py` / `battle_cog.py` settles through the same sporting rules as deadline resolve (shared settle helper; no first-click standings advantage)
- [x] T034 [US2] On matchday all-fixtures-terminal: complete matchday op, optional MoMD via existing RPC if retained, advance/`update` current matchday — invoked only from lifecycle engine
- [x] T035 [P] [US2] Add `tests/test_lifecycle_idempotency.py` pure/fake-store test: 100× `process_due_transitions` at fixed `now` settles each fixture/op once (mock DB layer acceptable)

**Checkpoint**: US2 independent — deadline resolution + forfeit math proven without needing promo UI

---

## Phase 5: User Story 3 — Eight-club pyramid + human-first promotion (Priority: P1)

**Goal**: Multi-division seating, bot fill/snapshot, finals, human-first promo/releg with reduce-movement and eligibility

**Independent Test**: 6 / 9 / 16 humans seat correctly; bots marked; promo sets never overlap; bots never take human promo slots; double_forfeit matches excluded from promo eligibility

### Implementation for User Story 3

- [x] T036 [US3] Finalize preparation seating to write `league_divisions` + `league_participants.division_id` / `participant_type` / bot rating snapshot using extended `seasonal_divisions.py` in prepare path (`league_lifecycle_engine.py`)
- [x] T037 [US3] Implement settlement promotion/relegation application updating `league_members.seasonal_division_tier` via human-first rules + `league_lifecycle_promo_min_eligible_matches` config; idempotent op `season:{id}:promotion`
- [x] T038 [US3] Persist immutable `league_final_standings` rows (movement labels champion/promoted/stayed/relegated) during settle in `league_lifecycle_engine.py`
- [x] T039 [US3] Enqueue outbox events for champion / promotion / relegation presentation; ensure bots receive no economy rewards on settle path
- [x] T040 [P] [US3] Extend `tests/test_seasonal_promo_relegation.py` (or add `tests/test_lifecycle_promo_human_first.py`) for human-first slots, reduce-movement, and double_forfeit non-eligibility

**Checkpoint**: US3 promo/releg demoable from settled V1 season data

---

## Phase 6: User Story 4 — Rulebook-driven automation, recovery, admin parity (Priority: P1)

**Goal**: Thin scheduler wake-up; catch-up after outage; pause/resume rebase; admin uses same transitions; no dual competitive brains

**Independent Test**: Kill bot 6h past deadline → restart settles once; pause 48h → resume shifts windows; admin Start calls same prepare op key as automation; 021 job body contains no divergent prize/registration rules

### Implementation for User Story 4

- [x] T041 [US4] Implement `apps/discord_bot/core/league_recovery.py`: stalled `league_operation_runs`, expired locks, unfinished `failed_retryable` fixtures, startup catch-up invoking `process_due_transitions`
- [x] T042 [US4] Implement pause/resume transitions with window rebase for unresolved matchdays/fixtures in `league_lifecycle_engine.py` (FR-010/invariants 10–11)
- [x] T043 [US4] Implement admin force-end → `cancelled` cancellation settlement (not natural completed; prizes/promo gated) in `league_lifecycle_engine.py`
- [x] T044 [US4] Refactor `apps/discord_bot/core/league_automation.py` into thin wake-up adapter: `process_due_transitions` + outbox flush + recovery only; grandfather Dynamics tick for non-V1 seasons remains explicit and separate from V1 rule evaluation
- [x] T045 [US4] Register ~5 minute interval + startup recovery in `apps/discord_bot/core/scheduler_jobs.py` and `apps/discord_bot/main.py` per research D10; ensure job does not embed registration/prize business rules
- [x] T046 [US4] Wire `/admin` Pause / Resume / Force End / Open Registration / Start Season to shared engine transitions in `apps/discord_bot/cogs/admin_cog.py` per `contracts/admin-and-hub-surfaces.md` (hide Open/Start when automation owns happy path on cutover guilds — same pattern as 021)
- [x] T047 [P] [US4] Add `tests/test_pause_resume_rebase.py` for window shift math after pause duration

**Checkpoint**: US4 — catch-up + admin parity + thin scheduler proven

---

## Phase 7: User Story 5 — Managers prepare via existing league surfaces (Priority: P2)

**Goal**: `/league` + `/admin` config for TZ/hour/cutover; hub shows Discord-local deadlines; no new player slash commands

**Independent Test**: Inventory commands — no new player lifecycle slash; hub shows `<t:…>` from frozen `window_end`; admin can set IANA TZ + hour before prepare

### Implementation for User Story 5

- [x] T048 [US5] Add `/admin` controls to set `guild_config.league_timezone`, `league_resolution_hour_local`, and per-guild `league_lifecycle_v1_enabled` in `apps/discord_bot/cogs/admin_cog.py` (validate IANA via `zoneinfo.ZoneInfo`)
- [x] T049 [US5] Update `/league hub` embed + fixtures copy in `apps/discord_bot/cogs/league_cog.py` to show frozen matchday `window_end` as Discord timestamps; distinguish V1 vs grandfather Dynamics copy lightly
- [x] T050 [US5] Ensure registration still uses `/league` Register writing `league_registrations` (and membership) during `registration_open` — update `league_cog.py` gates for V1 statuses
- [x] T051 [US5] Confirm saved league lineup / matchday plan surfaces used by assistant path remain on existing hub/squad flows — document any missing field wiring in battle/league cogs without adding new slash commands
- [x] T052 [P] [US5] Grep `app_commands.command` / `@bot.tree` for accidental new player lifecycle commands; fail task if any added beyond `/league` + existing hubs

**Checkpoint**: US5 UX complete; SC-006/SC-008 satisfied

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, SDD reconcile, quickstart validation

- [x] T053 [P] Update `change_log.md` with Lifecycle Rulebook V1 player-facing notes (21-day cycle, local deadline hour, assistant resolution, cutover)
- [x] T054 [P] Reconcile `.specify/specs/v1.0.0/league-mode-design.md` to point cutover guilds at `026` rulebook (grandfather 020/021)
- [x] T055 Run `specs/026-league-lifecycle-rulebook/quickstart.md` validation checklist on pilot guild (or shortened config hours); record gaps as follow-ups — do not invent dual modes
- [x] T056 Confirm weekly Division Rank still only updates from bot matches (grep league settle path for `league_points` writes); remove any accidental coupling
- [x] T057 Final integrity pass: every new function/RPC has a traced call site; superseded 021 competitive logic deleted or reduced to wake-up; `verify_required_schema.sql` green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: Start immediately
- **Phase 2 Foundational**: Depends on Setup — **BLOCKS all user stories**
- **Phase 3 US1 (MVP)**: Depends on Foundational
- **Phase 4 US2**: Depends on Foundational; practically needs US1 matchday rows (T025) for live fixtures — can unit-test forfeit/assistant in parallel earlier
- **Phase 5 US3**: Depends on Foundational + US1 prepare/settle skeleton (T024/T026)
- **Phase 6 US4**: Depends on US1 engine skeleton; integrates US2 settle for catch-up demos
- **Phase 7 US5**: Can start after Foundational for admin TZ fields; hub deadlines need US1 windows
- **Phase 8 Polish**: After desired stories complete

### User Story Dependencies

```text
Foundation
    ├── US1 (cycle) ──┬── US2 (resolve/forfeit)
    │                 ├── US3 (promo/finals)
    │                 └── US5 (hub deadlines)
    └── US4 (scheduler/recovery/admin parity) ← after US1 skeleton
```

### Parallel Opportunities

- T003 stub files; T004–T008 pure modules; T012–T014 tests after their modules
- T018–T019 cutover helpers/tests while migration applies (after T015 authored)
- US5 admin TZ UI (T048) parallel with US2 once Foundational done
- T053–T054 docs parallel in Polish

---

## Parallel Example: Foundational pure modules

```bash
# After T003 stubs exist, implement in parallel:
Task: "lifecycle_states.py"
Task: "operation_keys.py"
Task: "schedule.py"
Task: "forfeit_rules.py"
Task: "assistant_lineup.py"
```

## Parallel Example: User Story 1

```bash
# After engine skeleton T022:
Task: "outbox publisher T028"  # can proceed once T027 event shapes exist
Task: "smoke script T029"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 + Phase 2 (schema + pure rulebook + verify)
2. Complete Phase 3 US1 (cycle + outbox, still stub auto-resolve as “mark due” or minimal sim)
3. **STOP and VALIDATE** on pilot: registration → prepare → activate → artificial matchday complete → settle → next reg
4. Then US2 (real assistant resolve) → US3 (promo) → US4 (thin wake-up) → US5 (polish UX)

### Incremental Delivery

1. Foundation → pure tests green  
2. US1 MVP cycle  
3. US2 deadline resolution / forfeits  
4. US3 pyramid + promo ceremony  
5. US4 recovery + 5-min wake-up + admin parity  
6. US5 hub/admin surfaces + command inventory  
7. Polish + quickstart + change_log  

### Suggested MVP scope

**US1 only** after Foundational: proves the rulebook calendar and exclusive cutover without requiring full assistant/promo polish.

---

## Notes

- [P] = different files, no incomplete dependencies
- Never put competitive rules in `scheduler_jobs.py` — wake-up only
- Never rewrite living 020/021 windows
- Coins only via `apply_club_economy` / existing league RPCs
- No `discord` imports under `packages/`
- Commit after each task or logical group when implementing

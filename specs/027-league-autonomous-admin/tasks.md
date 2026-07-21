# Tasks: Autonomous League Administration Policy

**Input**: Design documents from `/specs/027-league-autonomous-admin/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md  
**Depends on**: `026-league-lifecycle-rulebook` engine/schema (`070`, `LeagueLifecycleEngine`, outbox, recovery) already in tree

**Tests**: Include plan-named unit/inventory tests (`test_league_time_validation.py`, `test_league_time_defaults_freeze.py`, `test_admin_surface_inventory.py`). No full Discord integration suite required.

**Locked decisions** (research.md):
- Discord: Server Settings → League Time only; Announcements stay; League Management removed
- Defaults: coalesce NULL → `UTC` / hour `0` (027 overrides prior `20` seed/UI)
- Cutover flag: not Discord-editable
- Operator recovery: `scripts/league_lifecycle_recover.py` + stalled recovery on wake
- Optional `072` only to align `game_config` default hour → `0`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before UI/engine policy work

- [x] T001 Grep `LeagueManagementView`, `league_admin_`, `LifecycleTimezoneModal`, `admin_open_registration`, `admin_start_season`, `admin_end_season`, `admin_toggle_pause`, `admin_force_sim`, `admin_run_league_cycle`, `league_lifecycle_v1_enabled` Discord writes in `apps/discord_bot/cogs/admin_cog.py`; confirm touch list matches `specs/027-league-autonomous-admin/plan.md`
- [x] T002 [P] Create stub `packages/leagues/leagues/league_time.py` (`from __future__ import annotations` + module docstring only)
- [x] T003 [P] Create stub `scripts/league_lifecycle_recover.py` (docstring + argparse skeleton; no engine calls yet)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure League Time helpers + optional default-hour alignment — **MUST complete before user-story UI/engine wiring**

**⚠️ CRITICAL**: Do not ship Discord surface changes or prepare-coalesce until helpers + validation tests exist

- [x] T004 Implement IANA validate / reject-raw-offset / parse hour / coalesce defaults (`UTC`, `0`) / preview strings in `packages/leagues/leagues/league_time.py` per `contracts/league-time-settings.md` and `data-model.md` (no Discord imports)
- [x] T005 Export League Time helpers from `packages/leagues/leagues/__init__.py`
- [x] T006 [P] Add `tests/test_league_time_validation.py` covering valid IANA accept, `UTC+5:45` / `GMT-4` reject, unknown zone reject, hour bounds `0..23`
- [x] T007 [P] Author optional `supabase/migrations/072_league_time_defaults.sql` to set `game_config.league_lifecycle_default_resolution_hour` → `'0'` (skip file if decide app-only coalesce is enough — document choice in migration comment or omit and note in T008)
- [x] T008 If T007 ships: extend `supabase/scripts/verify_required_schema.sql` only as needed; apply via `scratch/apply_migration_072.py` (clone prior apply pattern) and verify — otherwise mark N/A in task notes and proceed

**Checkpoint**: `pytest tests/test_league_time_validation.py -q` green; helpers usable from bot without Discord imports

---

## Phase 3: User Story 1 — Admins only set League Time (Priority: P1) 🎯 MVP

**Goal**: `/admin → Server Settings → League Time` is the only Discord schedule config; preview + IANA validation; changes apply next season only; cutover not editable here

**Independent Test**: Open `/admin` → Server Settings → League Time; save `Asia/Kathmandu` + `20`; preview shows local + UTC + next-season copy; invalid offset rejected; active season windows unchanged after save

### Tests for User Story 1

- [x] T009 [P] [US1] Add `tests/test_league_time_defaults_freeze.py` pure assertions: coalesce NULL→UTC/0; “guild preference change must not imply rewriting frozen season snapshot fields” (helper/predicate level)
- [x] T010 [P] [US1] Extend or add preview helper unit cases in `tests/test_league_time_validation.py` for required preview copy shape from `contracts/league-time-settings.md`

### Implementation for User Story 1

- [x] T011 [US1] Add `ServerSettingsView` (or equivalent) + hub button under `AdminHubView` in `apps/discord_bot/cogs/admin_cog.py` labeled **Server Settings** navigating to League Time
- [x] T012 [US1] Implement League Time modal/view in `apps/discord_bot/cogs/admin_cog.py` that validates via `packages/leagues` helpers, upserts only `guild_config.league_timezone` + `league_resolution_hour_local`, shows preview, never writes `league_lifecycle_v1_enabled`
- [x] T013 [US1] Remove cutover / lifecycle-mode field from any remaining timezone UI in `apps/discord_bot/cogs/admin_cog.py` (operator/DB only per research R4)
- [x] T014 [US1] Ensure League Time save path never updates `league_seasons` / `league_matchdays` / fixture window columns in `apps/discord_bot/cogs/admin_cog.py`
- [x] T015 [US1] Defer interactions immediately and map validation errors to clear ephemeral embeds in `apps/discord_bot/cogs/admin_cog.py`

**Checkpoint**: League Time UX works end-to-end; cutover not Discord-tunable; freeze invariant held at write path

---

## Phase 4: User Story 2 — League runs without admin babysitting (Priority: P1)

**Goal**: No Discord control can open/close/start/end/pause/advance/settle/force-sim/run-cycle; engine remains sole lifecycle authority; `/league hub` stays input-only

**Independent Test**: Admin hub inventory shows no League Management lifecycle controls; banned `custom_id`s absent; `/league hub` cannot open registration early

### Tests for User Story 2

- [x] T016 [P] [US2] Add `tests/test_admin_surface_inventory.py` asserting banned ids from `contracts/discord-admin-surfaces.md` (`league_admin_open_reg`, `league_admin_start`, `league_admin_end`, `league_admin_pause`, `league_admin_sim`, `league_admin_kick`, `league_admin_duration`, `league_admin_config`, `league_admin_run_cycle`, and legacy `league_admin_tz` if relocated) are absent from `apps/discord_bot/cogs/admin_cog.py` source

### Implementation for User Story 2

- [x] T017 [US2] Delete `LeagueManagementView` and all lifecycle button handlers (`open_reg`, `start`, `end`, `pause`, `force_sim`, `kick`, `duration`, `config`, `run_cycle`, old timezone under League Management) from `apps/discord_bot/cogs/admin_cog.py`
- [x] T018 [US2] Delete or stop registering dead admin helper entrypoints (`admin_open_registration`, `admin_start_season`, `admin_end_season`, `admin_toggle_pause`, `admin_force_sim`, `admin_run_league_cycle`, kick/duration/config helpers) in `apps/discord_bot/cogs/admin_cog.py` if nothing else calls them — grep callers first
- [x] T019 [US2] Confirm `AdminHubView` only exposes Announcements + Server Settings (+ Switch Server); remove League Management hub button in `apps/discord_bot/cogs/admin_cog.py`
- [x] T020 [P] [US2] Audit `apps/discord_bot/cogs/league_cog.py` for any lifecycle phase mutations (open registration, start season, advance matchday); remove or gate so hub only registers/withdraws/views/lineup within engine-opened windows
- [x] T021 [P] [US2] Grep `apps/discord_bot/` for remaining Discord-triggered lifecycle mutators (`force_cancel_season`, `pause_season`, `open_registration_season` from cog/views); ensure only engine/scheduler/operator script call sites remain

**Checkpoint**: `pytest tests/test_admin_surface_inventory.py -q` green; Discord cannot babysit lifecycle

---

## Phase 5: User Story 4 — Failures recover without Discord admin tools (Priority: P1)

**Goal**: Stalled-op recovery on wake + operator CLI retry through the same engine; alerts via structured logs; no Discord break-glass

**Independent Test**: Stop bot past a deadline or stall an op; run `python scripts/league_lifecycle_recover.py`; catch-up settles once; re-run does not duplicate rewards/promo

### Implementation for User Story 4

- [x] T022 [US4] Wire `recover_stalled_operations` into the regular lifecycle wake path in `apps/discord_bot/core/scheduler_jobs.py` (and/or `league_automation.py` wake adapter) so stalled recovery is not startup-only — keep job body free of competitive rules
- [x] T023 [US4] Add structured ERROR logging when retry limits / stuck ops are detected in `apps/discord_bot/core/league_recovery.py` (include guild_id, operation_key, season id)
- [x] T024 [US4] Implement `scripts/league_lifecycle_recover.py` per `contracts/operator-recovery.md`: optional `--guild-id`; run stalled recover → `process_due_transitions` → outbox publish; journal/trigger distinguishes `operator_recover`; exit non-zero on hard failure
- [x] T025 [US4] Ensure operator script and wake paths never direct-update standings/rewards or convert `ruleset_version` — only call existing engine/recovery/outbox modules from `apps/discord_bot/core/`
- [x] T026 [P] [US4] Document operator usage (env vars, example command) in `scripts/league_lifecycle_recover.py` module docstring and cross-link from `specs/027-league-autonomous-admin/quickstart.md` §6 if needed

**Checkpoint**: Manual recover + wake catch-up work without Discord admin controls

---

## Phase 6: User Story 3 — Defaults work without blocking the league (Priority: P2)

**Goal**: Unconfigured guilds prepare with `UTC` + `00:00`; engine never hard-fails solely for missing League Time

**Independent Test**: Guild with NULL TZ/hour still prepares; season freeze shows UTC/0; lifecycle not blocked

### Implementation for User Story 3

- [x] T027 [US3] Replace prepare hard-fail on missing TZ/hour in `apps/discord_bot/core/league_lifecycle_engine.py` with coalesce via `packages/leagues` League Time helpers (`UTC` / `0`)
- [x] T028 [US3] Freeze coalesced effective values onto `league_seasons.timezone`, `resolution_hour_local`, and `ruleset_snapshot` at prepare in `apps/discord_bot/core/league_lifecycle_engine.py`
- [x] T029 [US3] Align any remaining UI/copy defaults that still advertise hour `20` as the unconfigured default in `apps/discord_bot/cogs/admin_cog.py` (configured evening hours remain allowed; unconfigured = `00:00`)
- [x] T030 [P] [US3] Extend `tests/test_league_time_defaults_freeze.py` (or engine-facing pure test) so coalesce + freeze field mapping matches `contracts/league-time-settings.md`
- [x] T031 [US3] Optional non-blocking defaults notice: log-only or outbox informational event — MUST NOT gate `process_due_transitions` (skip outbox if YAGNI; document choice)

**Checkpoint**: NULL guild League Time no longer blocks V1 preparation

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Doc reconciliation, changelog, quickstart validation

- [x] T032 [P] Confirm `specs/026-league-lifecycle-rulebook/contracts/admin-and-hub-surfaces.md` matches 027 Discord policy (amend if any pause/force-end Discord wording remains)
- [x] T033 [P] Reconcile any stale admin lifecycle mentions in `specs/026-league-lifecycle-rulebook/spec.md` FR-012/FR-039/US4 Discord paths with a short “amended by 027” note (do not rewrite competitive rulebook)
- [x] T034 Update player/admin-facing notes in `change_log.md` for League Time–only admin + autonomous operation
- [x] T035 Run `pytest tests/test_league_time_validation.py tests/test_league_time_defaults_freeze.py tests/test_admin_surface_inventory.py -q` and fix failures
- [x] T036 Walk `specs/027-league-autonomous-admin/quickstart.md` scenarios 1–6 on a pilot guild (or document blocked steps with evidence)
- [x] T037 Grep `apps/discord_bot/` for resurrected `league_admin_` lifecycle ids and dead imports after cleanup; delete leftovers

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP League Time surface
- **US2 (Phase 4)**: After US1 (same `admin_cog.py`; strip remaining lifecycle once Server Settings exists)
- **US4 (Phase 5)**: After Foundational; can start in parallel with US1/US2 if staffed on different files (`scheduler_jobs.py` / `league_recovery.py` / `scripts/`) — sequentially safer after US2 so Discord break-glass is already gone
- **US3 (Phase 6)**: After Foundational; can parallelize with US1 on `league_lifecycle_engine.py` vs `admin_cog.py`; must complete before claiming full autonomy for unconfigured guilds
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational only
- **US2 (P1)**: Prefer after US1 (shared admin hub file)
- **US4 (P1)**: Foundational; prefer after US2 for product completeness
- **US3 (P2)**: Foundational; independent of US1 UI but complements autonomy

### Parallel Opportunities

- T002/T003 in Setup
- T006/T007 in Foundational
- T009/T010 in US1 tests
- T020/T021 in US2 audits
- T026 docstring vs other US4 work
- T032/T033 doc polish in parallel

---

## Parallel Example: After Foundational

```bash
# Different files — can parallelize:
# Dev A (US1): apps/discord_bot/cogs/admin_cog.py Server Settings + League Time
# Dev B (US3): apps/discord_bot/core/league_lifecycle_engine.py coalesce defaults
# Dev C (US4): apps/discord_bot/core/scheduler_jobs.py + scripts/league_lifecycle_recover.py

# Same file — sequential:
# US1 then US2 on admin_cog.py (add Server Settings, then delete League Management)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundational (helpers + validation tests)
3. Phase 3 US1 League Time UI
4. **STOP and VALIDATE** preview / IANA reject / next-season copy
5. Then US2 strip (required before calling Discord “safe”)

### Incremental Delivery

1. Setup + Foundational → helpers ready
2. US1 → League Time only path works
3. US2 → Discord cannot babysit
4. US4 → operator/wake recovery replaces break-glass
5. US3 → unconfigured guilds never stall
6. Polish → docs + quickstart + changelog

### Suggested MVP scope

**US1 + Foundational**, then immediately **US2** before production ship (US1 alone still leaves Force End / Pause if US2 deferred). Minimum shippable autonomy = **US1 + US2 + US4**; include **US3** before enabling unconfigured guilds in the wild.

---

## Notes

- [P] = different files, no incomplete dependencies
- Do not reintroduce Discord pause/force-end “temporarily”
- Competitive calendar/match/promo rules stay in `026` / engine — this feature is authority + League Time + recovery entry points
- Commit after each task or logical group when implementing
- Stop at checkpoints to validate each story independently

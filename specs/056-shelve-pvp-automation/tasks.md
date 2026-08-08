# Tasks: Shelve PvP and Fix Surviving Automations

**Input**: Design documents from `/specs/056-shelve-pvp-automation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included for US2/US3 — feature description and contracts explicitly require version-dedupe and reminder-window cases. US1 validated primarily via grep gate + battle smoke (no new PvP tests).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Bot: `apps/discord_bot/`
- Packages: `packages/`
- Migrations: `supabase/migrations/`
- Tests: `tests/` at repository root
- Specs: `specs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Lock inventory and working context before destructive cleanup

- [x] T001 Confirm cleanup inventory against HEAD using `specs/056-shelve-pvp-automation/contracts/cleanup-inventory.md` and pre-PvP baseline `1737df6` (list files that still exist vs already gone; note Academy keep `095`–`097` and automation keep `107`)
- [x] T002 [P] Snapshot shared-file PvP hunks for restore reference: `git show 1737df6:apps/discord_bot/cogs/battle_cog.py` and diffs for files listed in cleanup-inventory §4 into a short working note under `specs/056-shelve-pvp-automation/` only if needed for implementer (do not commit secrets)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Forward schema cleanup + version-changelog RPC redefine + schema guard strip — MUST complete before story sign-off on any environment with applied 098–106

**⚠️ CRITICAL**: Do not ship bot changes that assume PvP is gone until migration `108` is authored and `verify_required_schema.sql` no longer requires PvP objects. Version-only changelog RPC lives in the same migration so US2 is unblocked.

- [x] T003 Author forward migration `supabase/migrations/108_shelve_pvp_and_version_changelog.sql` that: (1) `DROP` all PvP tables/columns/flags/indexes/policies/RPCs from 098–106 with `IF EXISTS`; (2) restore shared CHECK constraints and rewritten shared functions (e.g. `acquire_match_lock`) from **097 definitions**; (3) `CREATE OR REPLACE` `claim_deployment_changelog` / `complete_deployment_changelog` so `p_deployment_key` is the **version string only** per `contracts/changelog-version-rpc.md`; (4) end with a guard block that requires 107 automation objects and **zero** PvP objects
- [x] T004 Strip all PvP table/column/function/policy requirements and signature branches from `supabase/scripts/verify_required_schema.sql` while retaining Academy + `topgg_vote_reminders` / changelog claim RPC guards
- [x] T005 [P] Add apply helper `scratch/apply_migration_108.py` following the pattern of `scratch/apply_migration_107.py`
- [x] T006 Delete obsolete PvP migration sources from the repo: `supabase/migrations/098_pvp_matchmaking_rivalries.sql` through `supabase/migrations/106_fix_ai_snapshot_positions.sql` (keep `095`–`097` and `107`)
- [x] T007 [P] Delete PvP apply/check scratch scripts listed in `contracts/cleanup-inventory.md` §5 (`scratch/apply_migration_098.py`…`106`, `scratch/check_053_*`, `scratch/check_pvp_*`, `scratch/enable_pvp_flags.py`, `scratch/reset_pvp_dark_state.py`, `scratch/pvp_soak_report.py`, `scratch/patch_practice_mode.py`, `scratch/test_ai_*.py`, `scratch/test_snap.py`, `scratch/verify_schema_103.py`) — do not delete Academy 095–097 or `apply_migration_107.py`

**Checkpoint**: Foundation ready — `108` exists, verify script is PvP-free, obsolete migration/scratch files removed. User story implementation can proceed (apply `108` on target DB before end-to-end validation).

---

## Phase 3: User Story 1 - Shelve PvP and Restore Classic Battle (Priority: P1) 🎯 MVP

**Goal**: Erase all active PvP product surfaces and restore `/battle` to Bot Battle + Friendly only (baseline `1737df6` mode UX), preserving Youth Academy and later non-PvP match-integrity fixes.

**Independent Test**: `/battle` shows only Bot Battle + Friendly; Bot Battle completes on original AI/bot path; product-tree grep for cleanup-inventory §7 tokens returns zero hits; Academy 095–097 paths untouched.

### Implementation for User Story 1

- [x] T008 [P] [US1] Delete dedicated PvP package and bot modules: `packages/pvp/`, `apps/discord_bot/core/pvp_match.py`, `apps/discord_bot/core/pvp_rpc.py`, `apps/discord_bot/embeds/pvp_embeds.py`, `apps/discord_bot/views/pvp_queue_view.py`, `apps/discord_bot/views/rivalries_view.py`, `apps/discord_bot/tasks/pvp_matchmaker_job.py`
- [x] T009 [P] [US1] Delete PvP tests: `tests/test_pvp_matchmaking.py`, `tests/test_pvp_reward_policy.py`, `tests/test_pvp_rivalry_math.py`, `tests/test_pvp_integrity_remediation.py`, `tests/test_pvp_ghost_backfill.py`, `tests/test_pvp_ghost_backfill_e2e.py`
- [x] T010 [P] [US1] Delete PvP feature specs directories `specs/053-pvp-matchmaking-rivalries/` and `specs/054-instant-pvp-backfill/`
- [x] T011 [P] [US1] Remove `packages/pvp` editable install / dependency entries from `requirements.txt` (and any sibling requirements files that list it)
- [x] T012 [US1] Restore `apps/discord_bot/cogs/battle_cog.py` to Bot Battle + Friendly only: remove Find Opponent / Ranked / Practice / queue / rivalry / ghost paths; keep post-PvP non-PvP integrity fixes (diff against `1737df6` and HEAD per research.md R5)
- [x] T013 [P] [US1] Strip PvP hunks from `apps/discord_bot/core/api_errors.py`
- [x] T014 [P] [US1] Strip PvP hunks from `apps/discord_bot/core/economy_rpc.py`
- [x] T015 [P] [US1] Strip PvP run types / helpers from `apps/discord_bot/core/match_runs.py`
- [x] T016 [P] [US1] Strip PvP recovery paths from `apps/discord_bot/core/match_recovery.py`
- [x] T017 [US1] Remove `pvp_ghost_refresh_job` (and any other PvP jobs) from `apps/discord_bot/core/scheduler_jobs.py`
- [x] T018 [US1] Update `apps/discord_bot/main.py`: drop `pvp_matchmaker_job` / `pvp_ghost_refresh_job` imports and scheduler registrations; **keep** `run_topgg_vote_reminders` and startup changelog trigger
- [x] T019 [P] [US1] Strip PvP prefs/UI remnants from `apps/discord_bot/cogs/squad_cog.py` if present
- [x] T020 [P] [US1] Strip PvP LP / match-point hooks from `packages/leagues/leagues/match_points.py` if present
- [x] T021 [US1] Remove PvP feature flags and matchmaking/rivalry language from `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md`
- [x] T022 [US1] Run product-tree grep gate from `contracts/cleanup-inventory.md` §7 across `apps/`, `packages/`, `supabase/`, `tests/` and fix any remaining hits (exclude git history)

**Checkpoint**: US1 MVP — classic `/battle` only; no PvP modules/jobs/flags; schema migration ready; Academy preserved.

---

## Phase 4: User Story 2 - Changelog Posts Only on New Version (Priority: P2)

**Goal**: Announce changelog only when a new `## [X.Y.Z]` header appears; same-version restarts (any commit) stay silent.

**Independent Test**: Same version + restart/different commit → 0 posts; new version header → exactly 1 post; body edit under current version → 0 posts; failed send remains retryable.

### Tests for User Story 2

- [x] T023 [P] [US2] Extend `tests/test_deployment_changelog.py` with version-only cases: same version different commit → no post; body edit → no post; new header → one post; claim without complete → retryable; dual-claim race → single completion (mock RPC/DB as existing tests do)

### Implementation for User Story 2

- [x] T024 [US2] Change `apps/discord_bot/core/deployment_changelog.py` so claim key is `entry.version` only (remove `f"{entry.version}:{commit[:7]}"`); keep channel resolution + embed builder; call `complete_deployment_changelog` only after successful send; pass commit as optional metadata only
- [x] T025 [US2] Align any callers/docs of deployment key format with version-only contract in `specs/056-shelve-pvp-automation/contracts/changelog-version-rpc.md` (and note supersession of 055 contract semantics)
- [x] T026 [US2] Run `pytest tests/test_deployment_changelog.py -q` and confirm all version-dedupe cases pass

**Checkpoint**: US2 — restarts silent; new version posts once.

---

## Phase 5: User Story 3 - Reliable Top.gg Vote Reminder (Priority: P3)

**Goal**: At most one DM or Store fallback per vote window; prefer Top.gg `next_vote_at`; Forbidden closes the window with one Store fallback.

**Independent Test**: One expired window → ≤1 DM; concurrent claims → ≤1 completion; Forbidden → fallback once then clear; schedule uses Top.gg next time when present.

### Tests for User Story 3

- [x] T027 [P] [US3] Extend `tests/test_topgg_vote_reminders.py` for: window-key completion authority; Forbidden sets handled + `fallback_pending`; Store clears once; `next_vote_at` preferred over `last_vote_at+12h`; transient failure then success still ≤1 notice

### Implementation for User Story 3

- [x] T028 [US3] Harden reminder completion in `apps/discord_bot/tasks/topgg_vote_reminder_job.py` so successful DM **and** `discord.Forbidden` mark the window handled (`reminder_sent_at` / equivalent) per `contracts/topgg-reminder-hardening.md`
- [x] T029 [P] [US3] Verify/fix upsert scheduling in `apps/discord_bot/core/topgg_vote.py` to prefer Top.gg `next_vote_at` with `last_vote_at + 12h` fallback; confirm all vote/store call sites use it
- [x] T030 [P] [US3] Confirm `apps/discord_bot/core/pending_notices.py` + Store wiring in `apps/discord_bot/cogs/store_cog.py` show fallback once and clear `fallback_pending` without re-DM for the same window; fix gaps if found
- [x] T031 [US3] Run `pytest tests/test_topgg_vote_reminders.py -q` and confirm hardening cases pass

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Apply schema, document player-facing change, full quickstart gate

- [x] T032 Apply `108` on target DB via `scratch/apply_migration_108.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) — must pass with no PvP requirements
- [x] T033 [P] Update player-facing `change_log.md` with a **new** version section documenting PvP shelved + changelog/reminder fixes (this new header is also the live proof of US2 after deploy)
- [x] T034 [P] Reconcile any residual PvP mentions in active docs under `.specify/` / README only if they claim PvP is live (do not rewrite git history)
- [x] T035 Execute validation checklist in `specs/056-shelve-pvp-automation/quickstart.md` (battle smoke, changelog silent/new-version, reminder, Academy spot-check, grep gate)
- [x] T036 Run combined automation tests: `pytest tests/test_deployment_changelog.py tests/test_topgg_vote_reminders.py -q`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** clean US1 schema sign-off and US2 RPC semantics
- **US1 (Phase 3)**: Depends on Foundational for migration/guard alignment; code deletes (T008–T011) may start once T006/T007 inventory is clear, but T022 grep gate assumes T003–T004 + module deletes done
- **US2 (Phase 4)**: Depends on Foundational (version RPC in `108`) + preferably US1 `main.py` still wiring changelog startup (T018 keeps it)
- **US3 (Phase 5)**: Depends on Foundational only for “107 retained”; can proceed in parallel with US2 after Phase 2; must not reintroduce PvP scheduler jobs removed in T018
- **Polish (Phase 6)**: Depends on US1–US3 implementation tasks complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no dependency on US2/US3 — **MVP**
- **US2 (P2)**: After Phase 2 (version RPC); independent of reminder hardening
- **US3 (P3)**: After Phase 2; independent of changelog key fix; keep coexistence with US1 scheduler cleanup

### Within Each User Story

- US1: delete dedicated artifacts → restore shared files → grep gate
- US2: failing/extended tests → `deployment_changelog.py` fix → pytest green
- US3: extended tests → job/upsert/fallback harden → pytest green

### Parallel Opportunities

- Phase 1: T002 parallel with T001 wrap-up
- Phase 2: T005 and T007 parallel after T003 started; T006 after objects listed in T003
- US1: T008, T009, T010, T011, T013–T016, T019, T020 parallel after Phase 2 checkpoint; T012/T017/T018 sequential on battle/scheduler/`main.py` coupling
- US2: T023 parallel before/alongside T024
- US3: T027, T029, T030 parallel; T028 before T031
- Polish: T033/T034 parallel after functional complete; T032 before final quickstart if DB required

---

## Parallel Example: User Story 1

```text
# After Phase 2 checkpoint, launch deletes together:
Task: T008 Delete packages/pvp + bot pvp_* modules
Task: T009 Delete tests/test_pvp_*.py
Task: T010 Delete specs/053 and specs/054
Task: T011 Remove packages/pvp from requirements.txt
Task: T013 Strip api_errors.py
Task: T014 Strip economy_rpc.py
Task: T015 Strip match_runs.py
Task: T016 Strip match_recovery.py

# Then sequential restore/wiring:
Task: T012 Restore battle_cog.py
Task: T017 Clean scheduler_jobs.py
Task: T018 Clean main.py scheduler
Task: T022 Grep gate
```

## Parallel Example: User Story 2 + 3 (after Phase 2)

```text
Developer A: T023 → T024 → T026 (changelog)
Developer B: T027 → T028/T029/T030 → T031 (reminders)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 + Phase 2 (`108` + verify + delete 098–106 sources)
2. Complete Phase 3 US1 (delete PvP, restore `/battle`)
3. Apply `108` on staging and smoke Bot Battle + Friendly
4. **STOP and VALIDATE** before automation polish if needed for a safe rollback deploy

### Incremental Delivery

1. Setup + Foundational → schema/tooling ready  
2. US1 → pre-PvP battle MVP  
3. US2 → changelog quiet on restart  
4. US3 → reminder correctness  
5. Polish → `change_log.md` new section + full quickstart  

### Parallel Team Strategy

1. Team finishes Phase 2 together  
2. Dev A: US1 shared restores (`battle_cog` / `main`)  
3. Dev B: US1 parallel deletes + verify leftovers  
4. Dev C: US2 + US3 automation fixes  

---

## Notes

- Cite **US-42** child only if a mutating PR touches integrity surfaces; this work is primarily deletion/restore — still avoid inventing parallel XP/coin pipes while editing `economy_rpc.py` / match flows
- Never wholesale-revert `a564992` (Academy) or `818cca2` (automations)
- Do not edit already-applied `098`–`107` in place on remote — only forward `108`
- `change_log.md` update in T033 must add a **new version header** (not only edit under an old one) so production announcement behavior matches US2
- Commit cadence: after Phase 2, after US1, after US2, after US3, after polish (only when user requests commits)

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T002 | 2 |
| Foundational | T003–T007 | 5 |
| US1 PvP shelve | T008–T022 | 15 |
| US2 Changelog | T023–T026 | 4 |
| US3 Reminders | T027–T031 | 5 |
| Polish | T032–T036 | 5 |
| **Total** | T001–T036 | **36** |

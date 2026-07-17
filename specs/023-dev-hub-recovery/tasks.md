# Tasks: Development Hub Recovery

**Input**: Design documents from `/specs/023-dev-hub-recovery/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pure-math unit tests from plan (`tests/test_fatigue_injury_math.py` extend) — required by AGENTS for non-trivial eligibility/batch-energy helpers. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Atomic `process_recovery_batch(p_owner_id, p_card_ids UUID[])` length 1–3; all-or-nothing energy
- Energy = `N × fatigue_recovery_energy` (default 5); grant = `fatigue_recovery_session` (default 40)
- **No** skill-drill slot consumption (`daily_drill_count` / `player_drill_daily_log` untouched)
- Hub **💚 Recover** multi-select → confirm → result; Training Drills skill-only
- Keep transfer-list + active-evolution gates; exclude injured / in-hospital / fatigue ≥ 100
- Migration: `066_dev_hub_recovery.sql`; **no new slash command**
- Optional: wrap `process_recovery_session` → batch of one, or DROP after grep clean

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema work

- [x] T001 Grep `process_recovery_session`, `RECOVERY_DRILL_ID`, `__recovery__`, `fatigue_recovery_energy`, `fatigue_recovery_session`, `StatDrillView`, `DevelopmentHubView` callers; confirm touch list matches `specs/023-dev-hub-recovery/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_066.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure helpers + batch RPC — **MUST complete before hub Recover UI and drills removal wiring that depends on the new RPC**

**⚠️ CRITICAL**: Do not ship hub Recover confirm or delete the old single-card path until migration apply + schema verify pass

- [x] T003 [P] Add `recovery_session_eligible` and `recovery_batch_energy` helpers in `packages/player_engine/player_engine/fatigue.py` per `data-model.md` (eligible: not injured, not in_hospital, fatigue &lt; 100; energy = N × per-player cost, N clamped/validated 1–3 at call sites)
- [x] T004 [P] Export new helpers from `packages/player_engine/player_engine/__init__.py`
- [x] T005 [P] Extend `tests/test_fatigue_injury_math.py` for eligibility edge cases (injured, hospital, full fatigue, tired OK) and batch energy scaling (1→5, 3→15 at default 5; custom per-player)
- [x] T006 Author `supabase/migrations/066_dev_hub_recovery.sql` implementing `process_recovery_batch` per `contracts/process-recovery-batch-rpc.md` (length 1–3, duplicate reject, lock club/cards, transfer + evo gates, single `apply_club_economy` debit source `recovery_batch`, fatigue updates, **no** drill-cap writes); include schema guard for `function:process_recovery_batch`
- [x] T007 In `066_dev_hub_recovery.sql`, redefine `process_recovery_session(BIGINT, UUID)` as a thin wrapper calling `process_recovery_batch` with a one-element array **or** DROP after documenting zero remaining callers — must not restore drill-slot consumption
- [x] T008 Extend `supabase/scripts/verify_required_schema.sql` with `function:process_recovery_batch` (correct `split_part`); keep/adjust `process_recovery_session` entry to match T007
- [x] T009 Apply migration via `scratch/apply_migration_066.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green

**Checkpoint**: Schema verified; `pytest tests/test_fatigue_injury_math.py -q` green; bot Recover wiring can begin

---

## Phase 3: User Story 1 — Recover from the Development Hub (Priority: P1) 🎯 MVP

**Goal**: `/development` exposes **Recover**; manager selects 1–3 players, confirms total energy, applies fatigue via batch RPC, refreshes hub

**Independent Test**: From `/development` → Recover → select one tired player → confirm → fatigue up, energy spent, 0 XP; never open Training Drills (quickstart §1)

### Implementation for User Story 1

- [x] T010 [US1] Add **💚 Recover** button on `DevelopmentHubView` in `apps/discord_bot/cogs/development_cog.py` that opens the Recover flow (defer / owner-check consistent with other hub buttons)
- [x] T011 [US1] Implement Recover selection view in `apps/discord_bot/cogs/development_cog.py` per `contracts/development-recover-ui.md`: multi-select `min_values=1` `max_values=3`, fatigue % in option descriptions, Continue enabled when ≥1 selected, Back to hub
- [x] T012 [US1] Implement Recover confirmation view/embed in `apps/discord_bot/cogs/development_cog.py`: list names, per-player grant, total energy `N × config`, 0 XP / 0 coins; Confirm / Cancel
- [x] T013 [US1] Wire Confirm → `defer` → `assert_not_in_match` → `db.rpc("process_recovery_batch", …)` → success followup + `show_hub` in `apps/discord_bot/cogs/development_cog.py`; disable controls on submit to reduce double-tap
- [x] T014 [US1] Load `fatigue_recovery_energy` / `fatigue_recovery_session` via existing game_config helper for Recover UI previews in `apps/discord_bot/cogs/development_cog.py`

**Checkpoint**: US1 demoable — single- and multi-player Recover from hub without drills

---

## Phase 4: User Story 2 — Training Drills Are Skill-Only (Priority: P1)

**Goal**: Training Drills UI/copy has zero Recovery Session options or advertising

**Independent Test**: Open Training Drills → no Recovery option; skill drill still runs (quickstart §4)

### Implementation for User Story 2

- [x] T015 [US2] Remove `RECOVERY_DRILL_ID`, Recovery `SelectOption`, recovery run branch, and recovery-only constructor params from `StatDrillView` in `apps/discord_bot/cogs/development_cog.py` per `contracts/drills-recovery-removal.md`
- [x] T016 [US2] Rewrite `show_training_menu` embed/placeholder copy in `apps/discord_bot/cogs/development_cog.py` to skill-drills-only (no Recovery Session CTA); keep TG passive fatigue as facility flavor only if already shown
- [x] T017 [US2] Grep `apps/discord_bot/` for `RECOVERY_DRILL_ID`, `__recovery__`, `Recover Fitness`, and drills-path `process_recovery_session` — confirm zero leftovers outside the new Recover flow

**Checkpoint**: US2 independently verifiable — drills cannot trigger Recover

---

## Phase 5: User Story 3 — Eligibility and Hospital Boundaries (Priority: P2)

**Goal**: Only eligible roster cards appear; injured/hospital/full fitness blocked; empty-state when none qualify

**Independent Test**: Injured / hospital / fatigue 100 excluded; tired non-academy roster included; empty roster → clear empty-state (quickstart §3)

### Implementation for User Story 3

- [x] T018 [US3] Filter Recover select candidates in `apps/discord_bot/cogs/development_cog.py` using `recovery_session_eligible` plus not retired / not academy; exclude active evo + transfer-listed when queries are cheap (same patterns as drills/fusion)
- [x] T019 [US3] Empty-state embed/message when no eligible Recover players in `apps/discord_bot/cogs/development_cog.py` (Hospital / full fitness guidance; use `empty_state_line` if it fits)
- [x] T020 [P] [US3] Update Hospital / injury mapped copy in `apps/discord_bot/core/api_errors.py` to point at Recover / `/development` (or Hospital), not Training Drills Recovery Session

**Checkpoint**: US3 gates visible in UI without relying on RPC-only failures

---

## Phase 6: User Story 4 — Affordability and Partial Failure Clarity (Priority: P2)

**Goal**: Clear total cost; insufficient energy / mid-flow ineligibility / double-tap do not partial-charge

**Independent Test**: 3-player confirm with low energy → zero fatigue changes; double confirm → at most one charge (quickstart §2, §5)

### Implementation for User Story 4

- [x] T021 [US4] Ensure confirm embed always shows **total** energy via `recovery_batch_energy` before RPC in `apps/discord_bot/cogs/development_cog.py`; reject Continue/Confirm client-side when selection empty or &gt;3 (UI max already)
- [x] T022 [US4] Map new batch RPC exception strings (`Select between 1 and 3 players`, `Duplicate players…`, `Insufficient action energy`, etc.) in `apps/discord_bot/core/api_errors.py`; re-enable view controls on failure after Confirm
- [x] T023 [US4] On Confirm failure paths in `apps/discord_bot/cogs/development_cog.py`, never call `show_hub` success refresh as if batch succeeded; keep ephemeral error via `_api_message`

**Checkpoint**: US4 failure modes match Development affordability patterns; all-or-nothing held by RPC + UI disable

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, SDD, changelog, smoke, rollback note

- [x] T024 [P] Add player-facing note to `change_log.md` (Recover on `/development`; drills skill-only; 5⚡×N; +40 fatigue)
- [x] T025 [P] Reconcile `.specify/specs/v1.0.0/spec.md` Development surface: Recover hub button; drills no longer host Recovery
- [x] T026 Grep repo for stale “Recovery Session” / Training Drills recovery wording in player-facing strings (`apps/discord_bot/`, `change_log.md`); leave intentional Recover-path naming consistent
- [x] T027 Optional: add `scratch/smoke_dev_hub_recovery.py` calling `process_recovery_batch` for 1 and 3 card ids (idempotent-safe on a test club) per plan
- [x] T028 Run `specs/023-dev-hub-recovery/quickstart.md` validation checklist (manual Discord walkthrough) and `pytest tests/test_fatigue_injury_math.py -q`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** US1 confirm wiring and any DROP of old RPC
- **US1 (Phase 3)**: Depends on Foundational (needs `process_recovery_batch`)
- **US2 (Phase 4)**: Can start after Setup (drills strip is mostly UI); prefer after Foundational if still calling old RPC from drills until removed
- **US3 (Phase 5)**: Depends on US1 selection view existing
- **US4 (Phase 6)**: Depends on US1 confirm + Foundational RPC
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — MVP
- **US2 (P1)**: Independent of US1 UI once drills no longer call recovery RPC; ship with or right after US1
- **US3 (P2)**: Builds on US1 select surface
- **US4 (P2)**: Builds on US1 confirm + batch RPC

### Parallel Opportunities

- T002 || T001 (setup)
- T003 || T004 || T005 (packages/tests) while drafting T006 SQL in parallel by another agent only if no file overlap — T003/T004 share package; prefer T005 after T003
- T015–T017 (US2) can proceed in parallel with T010–T014 (US1) once Foundational is done (different code regions in same file — **serialize** if one agent; two agents avoid same-file conflict)
- T020 || T024 || T025 (api_errors / docs)

---

## Parallel Example: Foundational helpers

```bash
# After T003 helpers exist:
Task: "Export helpers from packages/player_engine/player_engine/__init__.py"
Task: "Extend tests/test_fatigue_injury_math.py for eligibility + batch energy"
# Then sequentially:
Task: "Author 066_dev_hub_recovery.sql process_recovery_batch"
Task: "Extend verify_required_schema.sql"
Task: "Apply migration 066 + verify"
```

## Parallel Example: After Foundational (same-file caution)

```bash
# Prefer one agent on development_cog.py at a time:
# Agent A: US1 Recover views (T010–T014)
# Agent B: wait, then US2 drills strip (T015–T017)
# Parallel docs: T024 change_log.md + T025 v1.0.0 spec.md
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundational (migration + helpers + tests)
3. Phase 3 US1 Recover hub flow
4. **STOP and VALIDATE** quickstart §1
5. Then US2 drills cleanup before release (do not ship Recover + leftover drills Recovery)

### Incremental Delivery

1. Setup + Foundational → RPC ready
2. US1 → hub Recover works
3. US2 → drills skill-only (required for coherent release)
4. US3 → eligibility UX polish
5. US4 → affordability / error polish
6. Polish → changelog + SDD + quickstart

### Suggested MVP scope

**US1 + Foundational + US2** (Recover hub + drills removal). US3/US4 should land in the same release if possible (small deltas on the same views).

---

## Notes

- [P] = different files, no incomplete dependencies
- Do not leave `process_recovery_session` with drill-cap side effects after 066
- No new slash commands or Store physio SKUs
- Rollback: restore drills Recovery from git; remove hub Recover; revert/replace 066 RPCs; Hospital/passive untouched
- Commit only when user requests

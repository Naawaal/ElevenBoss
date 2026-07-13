# Tasks: Youth Academy Integration & Functional Workflow

**Input**: Design documents from `/specs/015-youth-academy/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pure-math unit tests listed in plan.md (`tests/test_youth_math.py`, `tests/test_academy_slots.py`) — required by AGENTS verification for non-trivial formulas. No full Discord integration suite.

**Locked decisions** (research.md / clarify):
- Hybrid: weekly free intake + paid scouting (P2)
- UI: `/profile` → Manage Academy (no `/academy` slash)
- Grandfather existing senior intake cards (`in_academy DEFAULT FALSE`)
- Storage: `player_cards.in_academy` (not parallel youth table)
- Growth: daily points → +OVR via `process_daily_academy_growth` — **not** `apply_card_xp`
- Migration: `060_youth_academy_workflow.sql`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US7 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema work

- [x] T001 Grep `process_youth_intake`, `youth_academy_level`, `YOUTH_ACADEMY_TIERS`, `store_facilities`, `youth_intake_notifier`, `apply_club_economy` callers; confirm touch list matches `specs/015-youth-academy/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_060.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, pure math, and RPCs every story needs — **MUST complete before UI/story wiring**

**⚠️ CRITICAL**: No Manage Academy / intake / growth / scout bot wiring until this phase is done and schema verify passes

- [x] T003 [P] Add `academy_slot_cap(level)` and scout tier cost/duration helpers in `packages/economy/economy/facility_effects.py` per `specs/015-youth-academy/data-model.md` slot ladder and scout table
- [x] T004 [P] Implement `packages/player_engine/player_engine/youth_math.py` per `specs/015-youth-academy/contracts/academy-growth-math.md` (`academy_daily_points`, `apply_academy_tick`, `star_band`, `is_promotion_ready`, `should_age_out`)
- [x] T005 [P] Export new helpers from `packages/economy/economy/__init__.py` and `packages/player_engine/player_engine/__init__.py`
- [x] T006 [P] Add `tests/test_youth_math.py` covering monotonic L5>L1 points, OVR ≤ POT, ready@65, age-out@20
- [x] T007 [P] Add `tests/test_academy_slots.py` covering slot caps 4/5/6/8/10 and clamp outside 1–5
- [x] T008 Author `supabase/migrations/060_youth_academy_workflow.sql`: columns `player_cards.in_academy`, `academy_progress`, `academy_seated_at`; `players.scouting_finishes_at`; table `scouting_reports` + RLS policies; `game_config` keys from data-model; schema guard block
- [x] T009 In `060_youth_academy_workflow.sql`, replace `process_youth_intake` body for academy seating per `contracts/process-youth-intake-seating.md`
- [x] T010 In `060_youth_academy_workflow.sql`, add `process_daily_academy_growth` mirroring `youth_math` + age-out promote/delete per `contracts/promote-release-academy.md` and `contracts/academy-growth-math.md`
- [x] T011 In `060_youth_academy_workflow.sql`, add `promote_academy_player` and `release_academy_player` per `contracts/promote-release-academy.md` (senior cap via `senior_roster_cap`)
- [x] T012 In `060_youth_academy_workflow.sql`, add `dispatch_youth_scout`, `finalize_youth_scout_report`, and `sign_youth_scout_prospect` using `apply_club_economy` per `contracts/scouting-dispatch-claim.md` — `finalize_youth_scout_report` handles the report insert path; `dispatch_youth_scout` MUST validate the open-report precondition (blocks dispatch if a claimable unsigned report is already open)
- [x] T013 Extend `supabase/scripts/verify_required_schema.sql` with new columns/table/RPCs/policies from 060
- [x] T014 Apply migration via `scratch/apply_migration_060.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green

**Checkpoint**: Schema verified; `pytest tests/test_youth_math.py tests/test_academy_slots.py -q` green; bot wiring can begin

---

## Phase 3: User Story 1 — Open the Academy and Understand Status (Priority: P1) 🎯 MVP

**Goal**: Managers open Manage Academy from /profile and see level, slots, prospect list, ready markers, next intake, help copy

**Independent Test**: Open `/profile` → Manage Academy; empty or seeded academy shows level, `used/cap`, help, next-intake hint without support docs

### Implementation for User Story 1

- [x] T015 [P] [US1] Create academy list/status embeds in `apps/discord_bot/embeds/academy_embeds.py` per `contracts/manage-academy-ui.md`
- [x] T016 [US1] Create `apps/discord_bot/views/academy_hub.py` with owner check, defer-on-click, prospect list render (read-only MVP: Back + refresh)
- [x] T017 [US1] Add **Manage Academy** button and YA field copy (slots + growth blurb) in `apps/discord_bot/views/store_facilities.py`
- [x] T018 [US1] Wire academy hub data fetch (`in_academy` cards, `youth_academy_level`, slot cap helper, next Monday UTC intake hint) in `apps/discord_bot/views/academy_hub.py`

**Checkpoint**: US1 independently demoable with empty academy and with manually seeded `in_academy` rows

---

## Phase 4: User Story 2 — Receive and Seat Intake Prospects (Priority: P1)

**Goal**: Monday intake seats into academy slots (not XI); skips when full; visible in Manage Academy even if DM missed

**Independent Test**: Run intake for a club with free slots → prospects appear in Manage Academy and are not auto-assigned to XI; full academy → `skipped > 0`, existing rows untouched

### Implementation for User Story 2

- [x] T019 [US2] Update intake DM/embed copy in `apps/discord_bot/embeds/youth_intake_embeds.py` (“seated in academy”, Manage Academy path, skipped note)
- [x] T020 [US2] Update `apps/discord_bot/tasks/youth_intake_notifier.py` to handle seating result payload (`seated`/`skipped`/`slots_*`) and DM accordingly
- [x] T021 [US2] Confirm `process_youth_intake` caller(s) only go through notifier/job; grep for leftover “join your roster” copy in `apps/discord_bot/`

**Checkpoint**: Intake seats academy-only; Manage Academy lists new prospects

---

## Phase 5: User Story 3 — Watch Academy Prospects Grow (Priority: P1)

**Goal**: Daily passive growth ticks update progress/OVR toward POT; list shows comparable progress

**Independent Test**: Note progress day 0; invoke `process_daily_academy_growth`; progress/OVR moves within formula and never exceeds POT

### Implementation for User Story 3

- [x] T022 [P] [US3] Add `apps/discord_bot/tasks/academy_growth_job.py` calling `process_daily_academy_growth` and logging age-out results
- [x] T023 [US3] Register daily job in `apps/discord_bot/core/scheduler_jobs.py` and `apps/discord_bot/main.py` (e.g. 00:10 UTC after `daily_recovery_job`)
- [x] T024 [US3] Show per-prospect progress toward next OVR (+ Ready badge) in `apps/discord_bot/embeds/academy_embeds.py` / `academy_hub.py`

**Checkpoint**: Growth job wired; hub reflects progress after a tick

---

## Phase 6: User Story 4 — Promote into the Senior Club (Priority: P1)

**Goal**: Promote academy → senior when under cap; early promote allowed; profile/squad treat as normal senior; block when full

**Independent Test**: Promote one prospect with free senior capacity → leaves academy, assignable in `/squad`; at cap → clear error

### Implementation for User Story 4

- [x] T025 [US4] Add Promote select/confirm flow calling `promote_academy_player` in `apps/discord_bot/views/academy_hub.py` (early-promote warning if OVR &lt; ready)
- [x] T026 [P] [US4] Reject `in_academy` cards on squad assign in `apps/discord_bot/cogs/squad_cog.py` with clear ephemeral
- [x] T027 [P] [US4] Exclude `in_academy` from marketplace sell list in `apps/discord_bot/cogs/marketplace_cog.py`
- [x] T028 [P] [US4] Exclude `in_academy` from development drill/fusion/mentor targets in `apps/discord_bot/cogs/development_cog.py`

**Checkpoint**: Promote works; academy cards cannot enter XI/sell/drill paths

---

## Phase 7: User Story 5 — Release Underperforming Prospects (Priority: P2)

**Goal**: Confirm release frees a slot; cancel leaves prospect unchanged

**Independent Test**: Release one academy prospect → gone from list; slots decrement by 1

### Implementation for User Story 5

- [x] T029 [US5] Add Release confirm flow calling `release_academy_player` in `apps/discord_bot/views/academy_hub.py` with clear “gone from club” copy
- [x] T030 [US5] Refresh hub embed after release/promote failure paths with friendly RPC error mapping in `apps/discord_bot/views/academy_hub.py` (extend `api_errors` only if needed)

**Checkpoint**: Full academy can free a slot via release

---

## Phase 8: User Story 6 — Paid Scouting Assignment (Priority: P2)

**Goal**: Spend coins on timed scout tiers; claim shortlist; sign ≤1 into free slot; block if full/insufficient coins

**Independent Test**: Dispatch quick → timer set & coins down; finalize → shortlist; sign one; second sign / full slots rejected

### Implementation for User Story 6

- [x] T031 [P] [US6] Add scout shortlist embed helpers (fog by tier) in `apps/discord_bot/embeds/academy_embeds.py`
- [x] T032 [US6] Add Scout tier buttons → `dispatch_youth_scout` in `apps/discord_bot/views/academy_hub.py` (acceptance: dispatch UI/RPC blocks when `finalize_youth_scout_report` has left an unclaimed claimable report pending)
- [x] T033 [US6] Add report finalize path (generate 3 prospects via existing youth generator + insert/claim RPC) and Sign control in `apps/discord_bot/views/academy_hub.py` / small helper under `apps/discord_bot/tasks/` if needed
- [x] T034 [US6] Optional scout-ready DM (hub remains source of truth) following `youth_intake_notifier` DM pattern; tolerate `discord.Forbidden`

**Checkpoint**: Hybrid scouting works without disabling Monday intake

---

## Phase 9: User Story 7 — Facility Level as Meaningful Academy Power (Priority: P2)

**Goal**: Facilities + Manage Academy publish slots, quality band, and growth benefit by YA level; upgrade rules unchanged

**Independent Test**: Compare L1 vs L5 copy side-by-side on Facilities/Manage Academy — slots and bands match spec ladder

### Implementation for User Story 7

- [x] T035 [US7] Update Youth Academy field in `apps/discord_bot/views/store_facilities.py` to show current slots, intake OVR/POT/gem band, and growth rate blurb (not only upgrade cost)
- [x] T036 [US7] Ensure Manage Academy header uses same slot/quality helpers so Facilities and Academy stay consistent

**Checkpoint**: Upgrading YA clearly changes published capacity/quality/growth messaging

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, SDD reconcile, persona validation

- [x] T037 [P] Update player-facing `change_log.md` for academy holding phase, Manage Academy path, hybrid scouting
- [x] T038 [P] Reconcile `.specify/specs/v1.0.0/spec.md` (and plan.md if needed) for US-32/US-33 academy seating + Manage Academy (FR-aligned)
- [x] T039 Grep confirm zero remaining “prospects join your roster” / hardcoded academy growth XP via `apply_card_xp`; confirm every new RPC has a call site
- [x] T040 Run `specs/015-youth-academy/quickstart.md` validation checklist (pytest + schema + persona unhappy paths: DM off, double-tap, full slots, senior cap)
- [x] T041 Age-out notification path: DM or hub banner from `process_daily_academy_growth` result in `apps/discord_bot/tasks/academy_growth_job.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup** → no deps
- **Phase 2 Foundational** → after Setup; **blocks all user stories**
- **US1 (Phase 3)** → after Foundational (MVP UI)
- **US2 (Phase 4)** → after Foundational; best after US1 so seating is visible in hub
- **US3 (Phase 5)** → after Foundational; best after US1 for progress display
- **US4 (Phase 6)** → after US1 (needs promote UI); exclusions can parallelize
- **US5 (Phase 7)** → after US1
- **US6 (Phase 8)** → after US1 + Foundational scout RPCs; independent of US3
- **US7 (Phase 9)** → after US1 (copy polish; can overlap US2)
- **Polish** → after desired stories (recommend after US1–US7)

### User Story Dependencies

| Story | Depends on | Independently testable? |
|-------|------------|-------------------------|
| US1 Manage Academy | Foundational columns | Yes (empty/seeded rows) |
| US2 Intake seating | Foundational intake RPC; US1 for visibility | Yes via RPC + list |
| US3 Growth | Foundational growth RPC; US1 for UI | Yes via manual RPC |
| US4 Promote | US1 hub; Foundational promote RPC | Yes |
| US5 Release | US1 hub; Foundational release RPC | Yes |
| US6 Scouting | US1 hub; Foundational scout RPCs | Yes |
| US7 Facility copy | US1 | Yes (copy-only) |

### Parallel Opportunities

- T003–T007 (pure packages + tests) in parallel during Foundational
- T015 embeds || early hub skeleton once schema exists
- T026–T028 exclusions in parallel during US4
- T031 scout embeds || T032–T033 after dispatch RPC live
- T037–T038 docs in parallel during Polish

---

## Parallel Example: Foundational pure layer

```text
Task: "academy_slot_cap + scout helpers in packages/economy/economy/facility_effects.py"
Task: "youth_math.py in packages/player_engine/player_engine/youth_math.py"
Task: "tests/test_youth_math.py"
Task: "tests/test_academy_slots.py"
```

## Parallel Example: User Story 4 exclusions

```text
Task: "Reject in_academy in apps/discord_bot/cogs/squad_cog.py"
Task: "Exclude in_academy in apps/discord_bot/cogs/marketplace_cog.py"
Task: "Exclude in_academy in apps/discord_bot/cogs/development_cog.py"
```

---

## Implementation Strategy

### MVP First (US1 + Foundational)

1. Phase 1–2 (migration + math + verify)
2. Phase 3 US1 Manage Academy read-only
3. **STOP and VALIDATE** quickstart §3
4. Then US2 seating (makes academy real) → US3 growth → US4 promote as P1 vertical slice

### Suggested ship slices

1. **MVP**: Foundational + US1 + US2 + US3 + US4 (hold → grow → promote)
2. **Complete v1**: + US5 release + US6 scouting + US7 copy + Polish

### Incremental delivery

1. Setup + Foundational → schema green  
2. US1 → demo Manage Academy  
3. US2 → Monday seats academy  
4. US3 → daily growth  
5. US4 → promote + exclusions  
6. US5 → release  
7. US6 → paid scout sink  
8. US7 + Polish → changelog / SDD / quickstart sign-off  

---

## Notes

- No new slash commands
- Coins only via `apply_club_economy`; academy growth never via `apply_card_xp`
- Grandfather: never backfill `in_academy=true` on existing cards
- Commit after each phase checkpoint when user requests commits
- Stop at any checkpoint to validate the story independently

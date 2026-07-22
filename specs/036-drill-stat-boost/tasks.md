# Tasks: Drill Attribute Boost

**Input**: Design documents from `/specs/036-drill-stat-boost/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by plan/quickstart — `tests/test_drill_stat_boost.py` (parser + preview gates); keep `tests/test_progression_caps.py` green if shared gates touched.

**Locked decisions** (research.md):
- Soft-fail attribute boost; XP + costs always complete when drill hard-gates pass
- Pre-check with `peek_card_ovr` — do **not** use allocate’s apply-then-`RAISE` (would roll back XP/coins)
- Always `+1` (tier affects cost/XP only); six single-stat drills only
- Migration `078_drill_stat_boost.sql` from latest **075** `process_stat_drill` body; keep `assert_card_action_allowed(..., 'drill')`
- No new tables / slash commands / drill ids; amend AGENTS + v1.0.0 “XP only” on polish

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]` / `[US2]` / `[US3]` maps to spec user stories

---

## Phase 1: Setup

**Purpose**: Confirm touch list before writing code

- [x] T001 Grep `process_stat_drill`, `peek_card_ovr`, `parse_stat_drill_result`, `STAT_DRILLS`, `can_allocate_skill_point`, `OVR unchanged`, `XP only` across `supabase/migrations/`, `apps/discord_bot/`, `packages/player_engine/`, `AGENTS.md`, `.specify/specs/v1.0.0/`; confirm touch list matches `plan.md`

---

## Phase 2: Foundational — `process_stat_drill` boost + soft-fail (BLOCKS all stories)

**Purpose**: Atomic RPC grants optional `+1` with pot/99 soft-fail while preserving XP/economy and US-42.2 drill assert

**⚠️ CRITICAL**: No user-story UI/verify work until this migration file exists (apply can wait until US1 verify)

- [x] T002 Create `supabase/migrations/078_drill_stat_boost.sql`: `CREATE OR REPLACE FUNCTION public.process_stat_drill(bigint, uuid, text)` basing body on latest definition in `supabase/migrations/075_player_card_state_guards.sql` (retain `assert_card_action_allowed(..., 'drill')`, match lock, transfer-list lock, soft-reset, 20/5 caps, `apply_club_economy`, `apply_card_xp`)
- [x] T003 In same migration as T002: map `p_drill_id` → stat column; soft-fail eligibility via 99 / `overall >= potential` / `peek_card_ovr(... , stat+1) > potential` per `contracts/process-stat-drill-boost.md`; on success `UPDATE` +1 + `recalculate_card_ovr`; never `RAISE` for pot/99; never decrement `skill_points`
- [x] T004 In same migration as T002–T003: return additive JSON keys `stat_boosted`, `stat`, `stat_delta`, `new_stat_value`, `new_ovr`, `boost_block_reason` while keeping existing `xp_gain` / `cost` / `daily_*` / `economy` / `progression` keys; order = eligibility peek → charge/counters → optional write → XP
- [x] T005 [P] Add `scratch/apply_migration_078.py` following latest scratch apply pattern (e.g. `scratch/apply_migration_077.py` or `076`)
- [x] T006 Confirm `supabase/scripts/verify_required_schema.sql` still guards `process_stat_drill(bigint,uuid,text)` (extend only if new required objects appear — none expected)

**Checkpoint**: Migration encodes FR-001…FR-005 server-side; ready for client + story verify

---

## Phase 3: User Story 1 — Feel a focused training payoff (Priority: P1) 🎯 MVP

**Goal**: Uncapped drills grant XP **and** `+1` to the mapped attribute; summary shows the gain

**Independent Test**: Run Finishing Drill on an eligible uncapped card → XP + `+1 SHO` (and updated OVR if formula moved)

### Tests

- [x] T007 [P] [US1] Create `tests/test_drill_stat_boost.py`: assert `parse_stat_drill_result` reads boosted payload (`stat_boosted`, `stat`, `stat_delta`, `new_stat_value`, `new_ovr`) and defaults safely when boost keys missing

### Implementation

- [x] T008 [US1] Extend `parse_stat_drill_result` in `apps/discord_bot/core/drill_rpc.py` per `contracts/process-stat-drill-boost.md` (boost fields + safe defaults)
- [x] T009 [US1] Update post-drill success summary in `StatDrillView.run_drill_callback` (`apps/discord_bot/cogs/development_cog.py`): when `stat_boosted`, show `+1 {STAT}` / new value / `new_ovr`; remove unconditional “OVR unchanged — spend skill points…” for boosted runs
- [x] T010 [US1] Apply `078` via `scratch/apply_migration_078.py` on target DB; SQL or Discord check uncapped Finishing Drill → attribute +1 and XP both applied (SC-001)

**Checkpoint**: US1 MVP demoable after bot refresh — drills feel tangible when uncapped

---

## Phase 4: User Story 2 — Cap blocks attribute, not the whole drill (Priority: P1)

**Goal**: At 99 or pot ceiling, drill still completes (XP + costs); attribute unchanged; clear block reason

**Independent Test**: Card at attr 99 or where `+1` would exceed potential → XP granted, attr unchanged, reason visible, counters/energy/coins consumed

### Tests

- [x] T011 [P] [US2] Extend `tests/test_drill_stat_boost.py`: parser maps `boost_block_reason` values (`stat_at_maximum`, `at_potential`, `would_exceed_potential`) and `stat_boosted=false` / `stat_delta=0`

### Implementation

- [x] T012 [US2] In `StatDrillView.run_drill_callback` (`apps/discord_bot/cogs/development_cog.py`): when not boosted, show humanized block reason per `contracts/drill-hub-stat-copy.md`; confirm XP/cost lines still present; optional Allocate Skills hint OK
- [x] T013 [P] [US2] Optional `scratch/smoke_drill_stat_boost_078.py` (or SQL notes in quickstart): scripted blocked case proves soft-fail — no attribute write, XP path succeeds
- [x] T014 [US2] Manual/SQL verify per `quickstart.md` card **B**: blocked boost + XP + costs; Allocate Skills still works and was not charged by the drill (FR-008)

**Checkpoint**: SC-002 — capped cards still train for XP without silent or hard-fail attribute path

---

## Phase 5: User Story 3 — Preview and summary honesty (Priority: P2)

**Goal**: Drill picker and menu set expectations; summary distinguishes XP+boost vs XP-only blocked

**Independent Test**: Uncapped select shows `+1 XXX`; capped select does not promise guaranteed `+1`; after run, hub refresh reflects new ratings

- [x] T015 [US3] Update Training Drills menu blurb in `show_training_menu` (`apps/discord_bot/cogs/development_cog.py`) per `contracts/drill-hub-stat-copy.md` — XP **and** attempted attribute boost (not XP-only)
- [x] T016 [US3] Update drill `SelectOption` descriptions in `StatDrillView._build_items` (`apps/discord_bot/cogs/development_cog.py`): use `can_allocate_skill_point` (or equivalent) on selected card — show `+1 XXX` when allowed, else capped/at-potential hint, keep XP · energy preview
- [x] T017 [P] [US3] Extend `tests/test_drill_stat_boost.py` (or tiny pure helper test): preview gate agrees with `can_allocate_skill_point` for uncapped vs 99 / at-pot cases using catalog `stat` from `packages/player_engine/player_engine/drill_catalog.py`

**Checkpoint**: SC-003 — managers can trust preview + summary without opening a separate profile

---

## Phase 6: Polish & Cross-Cutting

- [x] T018 [P] Amend `AGENTS.md` §7 drills bullet — drills grant XP **and** soft-capped `+1` attribute (not XP-only)
- [x] T019 [P] Brief reconcile in `.specify/specs/v1.0.0/spec.md` / `plan.md` — amend AC-23f / “XP only” drill wording to match this feature
- [x] T020 Update `change_log.md` — player-facing: Training Drills grant `+1` to the trained attribute when under caps; XP still always awarded
- [x] T021 Run `pytest tests/test_drill_stat_boost.py tests/test_progression_caps.py -q`; run schema verify; walk `specs/036-drill-stat-boost/quickstart.md`; confirm no new slash commands / hub buttons / tables

---

## Dependencies & Execution Order

### Phase Dependencies

```text
T001
 → T002 → T003 → T004 → T006     (migration body; T005∥ once file exists)
 → T005 [P]
 → T007 [P] → T008 → T009 → T010 (US1 MVP)
 → T011 [P] → T012 → T014        (US2; T013∥ optional smoke)
 → T013 [P]
 → T015 → T016 → T017 [P]        (US3)
 → T018 [P], T019 [P], T020 → T021
```

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Blocks all user stories
- **US1 (Phase 3)**: After foundational — MVP
- **US2 (Phase 4)**: After US1 parser exists (shares `drill_rpc` / summary); independently testable on capped cards
- **US3 (Phase 5)**: After US1/US2 summary paths exist; preview can be built in parallel with US2 messaging if careful on same cog file
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Independently testable? |
|-------|------------|-------------------------|
| US1 (P1) | Phase 2 | Yes — uncapped boost + XP |
| US2 (P1) | Phase 2 + parser (T008) | Yes — capped soft-fail + XP |
| US3 (P2) | Phase 2; best after T009/T012 copy patterns | Yes — preview/menu honesty |

### Parallel Opportunities

- T005 ∥ T006 after T002–T004 written
- T007 ∥ start of T008 once contract known
- T011 ∥ T013 after RPC applied
- T017 ∥ docs T018/T019
- US2 messaging (T012) and US3 menu (T015) touch the same cog — **serialize** or one agent owns `development_cog.py`

---

## Parallel Example: User Story 1

```text
# After Phase 2 migration file exists:
Task: T007 — tests/test_drill_stat_boost.py boosted parser cases
Task: T005 — scratch/apply_migration_078.py (if not done)

# Then sequential on client:
Task: T008 — drill_rpc.py parser
Task: T009 — development_cog.py boosted summary
Task: T010 — apply + uncapped verify
```

---

## Parallel Example: User Story 2

```text
Task: T011 — blocked-reason parser tests
Task: T013 — optional smoke script
# Then:
Task: T012 — blocked summary copy in development_cog.py
Task: T014 — manual capped verify
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup (T001)
2. Phase 2 Migration 078 (T002–T006)
3. Phase 3 US1 parser + summary + apply (T007–T010)
4. **STOP and VALIDATE**: uncapped drill shows XP + `+1`
5. Continue US2/US3 before calling the feature done for players near pot

### Incremental Delivery

1. Setup + Foundational → RPC ready
2. US1 → tangible boost MVP
3. US2 → soft-fail honesty (required for pot/99 cards)
4. US3 → preview trust
5. Polish → AGENTS / SDD / changelog / quickstart

### Suggested MVP scope

**T001–T010** (Setup + Foundational + US1). Ship US2 before wide announce so capped cards don’t look broken.

---

## Notes

- [P] = different files, no incomplete dependencies
- Do not drop `assert_card_action_allowed` when replacing `process_stat_drill`
- Do not hard-fail the whole drill for pot/99
- Out of scope: multi-stat drills, changing 20/5 caps, spending SP on drills, Recover/fusion/evolution

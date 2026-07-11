# Tasks: Mentor Transfusion

**Input**: Design documents from `/specs/006-mentor-transfusion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require `tests/test_mentor_math.py` (conversion, eligibility, headroom, max units). Discord/RPC paths validated via `quickstart.md` (no Discord integration test harness required).

**Organization**: Tasks grouped by user story (US1–US5) for incremental delivery.

**Locked decisions** (from research.md R1–R6):
- SP debit: `skill_points -= 5N` and `skill_points_spent += 5N`
- Reject transfers that would waste XP; Max = `mentor_max_units(source_sp, target_xp)`
- Source eligible: `overall >= potential` and `skill_points >= 5`
- Target eligible: same club, `overall < potential`, `level < L_MAX`, headroom ≥ 500×N
- Append-only `mentor_transfer_log`; daily cap `COUNT(*) < 3` per club/UTC date
- Profile = Mentor Ready copy only (no new CTA); busy lock = `assert_not_in_match` only
- XP via `apply_card_xp(..., 'mentor_transfer')` only; migration `052+`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 / US5
- Include exact file paths in descriptions

## Path Conventions

- Pure engine: `packages/player_engine/player_engine/`
- Bot: `apps/discord_bot/`
- SQL: `supabase/migrations/`, `supabase/scripts/verify_required_schema.sql`
- Tests: `tests/` at repo root
- Scratch: `scratch/`
- SDD: `.specify/specs/v1.0.0/`
- Feature docs: `specs/006-mentor-transfusion/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm contracts and call sites before code

- [x] T001 Review `specs/006-mentor-transfusion/plan.md` against `contracts/mentor-math.md`, `contracts/transfer-mentor-xp-rpc.md`, and `contracts/development-mentor-ui.md`; note any drift in `specs/006-mentor-transfusion/research.md` if found
- [x] T002 [P] Grep `apps/discord_bot/cogs/development_cog.py`, `apps/discord_bot/cogs/player_cog.py`, and `apps/discord_bot/core/api_errors.py` for `show_skills_menu`, `allocate_skill_point`, `skill_points`, and fusion subview patterns; list exact insertion points for mentor UI and error mapping

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure math + schema/RPC + error mapping that all stories need

**⚠️ CRITICAL**: Do not ship Discord mentor UI until migration `052` is applied and `verify_required_schema.sql` passes

- [x] T003 Implement `packages/player_engine/player_engine/mentor_math.py` per `contracts/mentor-math.md` (`SP_PER_MENTOR_UNIT`, `XP_PER_MENTOR_UNIT`, `MENTOR_TRANSFERS_DAILY_LIMIT`, `sp_to_mentor_units`, eligibility helpers, `xp_headroom_to_max`, `mentor_max_units`, `preview_mentor_transfer` using `simulate_apply_card_xp`)
- [x] T004 [P] Export mentor constants and helpers from `packages/player_engine/player_engine/__init__.py`
- [x] T005 [P] Create `tests/test_mentor_math.py` asserting 5→1→500 conversion, source/target eligibility, headroom, `mentor_max_units`, and invalid preview when waste would occur
- [x] T006 Create `supabase/migrations/052_mentor_transfusion.sql` per `data-model.md` and `contracts/transfer-mentor-xp-rpc.md`: table `mentor_transfer_log` + RLS/policies, RPC `transfer_mentor_xp` (lock → validate → debit SP/spent → `apply_card_xp(..., 'mentor_transfer')` → INSERT log → JSONB return), migration-end schema guard
- [x] T007 [P] Add `scratch/apply_migration_052.py` (follow existing scratch apply pattern) and extend `supabase/scripts/verify_required_schema.sql` for `table:public.mentor_transfer_log`, `function:transfer_mentor_xp`, and required policy entries
- [x] T008 Map mentor RPC exception message fragments to manager-facing copy in `apps/discord_bot/core/api_errors.py` (insufficient SP, not maxed source, maxed target, daily limit, ownership, headroom/absorb)

**Checkpoint**: `pytest tests/test_mentor_math.py -q` green; migration applies; verify passes; no Discord mentor button yet

---

## Phase 3: User Story 1 — Transfer Mentor Progress From a Maxed Card (Priority: P1) 🎯 MVP

**Goal**: Manager can complete one atomic Mentor Transfer (SP debit → target XP) from Development

**Independent Test**: Maxed source (≥5 SP) + eligible target → confirm 1 MP → source SP −5, target XP +500 (or level-up), log row created, daily count increments

### Implementation for User Story 1

- [x] T009 [US1] Add a short-lived Mentor Transfer confirm path in `apps/discord_bot/cogs/development_cog.py` that: `defer`s, runs `assert_not_in_match`, calls `db.rpc("transfer_mentor_xp", {p_owner_id, p_source_card_id, p_target_card_id, p_mentor_units})`, and shows success/failure via `api_error_message` / followup embed
- [x] T010 [US1] Wire a minimal entry from Allocate Skills when `overall >= potential` and `skill_points >= 5`: **Mentor Transfer** button → target select (eligible club mates) → confirm **1 MP** (hardcoded unit for MVP if amount UI not yet built) → T009 handler
- [x] T011 [US1] On success, refresh displayed source SP and target level/XP from RPC JSON (`source_skill_points`, `xp_result`) in `apps/discord_bot/cogs/development_cog.py`
- [x] T012 [US1] Grep `apps/discord_bot/` to confirm mentor path never updates `players.coins`, energy columns, or calls `apply_card_xp` directly from Python

**Checkpoint**: One end-to-end transfer works on a test club after migration apply (quickstart §1 happy path at 1 MP)

---

## Phase 4: User Story 2 — Discover Mentor From Development Allocate Skills (Priority: P1)

**Goal**: Maxed cards show Mentor Ready instead of a dead-end allocate experience; non-maxed allocate unchanged

**Independent Test**: Open Allocate Skills on maxed (≥5 SP), maxed (&lt;5 SP), and non-maxed cards — only eligible maxed offers working Mentor Transfer; non-maxed still has six stat buttons

### Implementation for User Story 2

- [x] T013 [US2] Branch `show_skills_menu` / skills embed in `apps/discord_bot/cogs/development_cog.py` per `contracts/development-mentor-ui.md`: Mentor Ready copy (SP + convertible MP) when `overall >= potential`; hide or disable the six allocate buttons when maxed
- [x] T014 [US2] When maxed and `0 < skill_points < 5`, show clear “need 5 SP” guidance and keep Mentor Transfer disabled/grey (no silent failure)
- [x] T015 [US2] Verify non-maxed path still lists roster + six `allocate_skill_point` buttons unchanged in `apps/discord_bot/cogs/development_cog.py`
- [x] T016 [P] [US2] Optional: respect `MENTOR_TRANSFUSION_ENABLED` env (default on) to hide mentor chrome in `apps/discord_bot/cogs/development_cog.py` without removing RPC

**Checkpoint**: Discovery UX matches FR-008 / quickstart §2–§3

---

## Phase 5: User Story 3 — Choose Target and Amount With Preview (Priority: P2)

**Goal**: Target picker + amount buttons + confirmation preview before commit

**Independent Test**: Select target, try 1/3/5/Max, cancel once (no writes), confirm once (writes); preview matches 5N SP / 500N XP / simulated levels

### Implementation for User Story 3

- [x] T017 [US3] Replace MVP single-unit confirm with target select sorted by `level ASC` then name in `apps/discord_bot/cogs/development_cog.py` (eligible: same club, `overall < potential`, `level < 100`, not source)
- [x] T018 [US3] Add amount buttons **[1 MP] [3 MP] [5 MP] [Max]** using `mentor_max_units`; disable amounts above max in `apps/discord_bot/cogs/development_cog.py`
- [x] T019 [US3] Build confirmation embed from `preview_mentor_transfer` / `simulate_apply_card_xp` showing SP spent, MP, XP, level before→after, and Cancel that writes nothing
- [x] T020 [US3] If `development_cog.py` grows unwieldy, extract mentor views/embeds to `apps/discord_bot/embeds/mentor_embeds.py` (or adjacent views module) without new slash commands

**Checkpoint**: Quickstart §1 full amount/preview path; cancel safety verified

---

## Phase 6: User Story 5 — Daily Transfer Pacing (Priority: P2)

**Goal**: Club limited to 3 successful transfers per UTC day with clear UX

**Independent Test**: Three successes then fourth rejected with clear daily-limit message and unchanged balances; next UTC day allows transfers again

### Implementation for User Story 5

- [x] T021 [US5] Show `transfers_used_today` / `transfers_remaining_today` on confirm and success embeds in `apps/discord_bot/cogs/development_cog.py` (from RPC JSON or pre-count query)
- [x] T022 [US5] Confirm `api_errors.py` maps daily-limit RPC errors to clear manager copy; double-tap Confirm cannot create a 4th success (RPC count + row locks)
- [x] T023 [US5] Manually validate quickstart §4 (three transfers + blocked fourth) against applied `052` DB

**Checkpoint**: FR-006 / SC-003 satisfied; fusion daily log remains independent

---

## Phase 7: User Story 4 — See Mentor Ready on Player Profile (Priority: P3)

**Goal**: Maxed card profiles surface Mentor Ready conversion; non-maxed profiles unchanged

**Independent Test**: Profile on maxed vs non-maxed — only maxed shows Mentor Ready MP/XP line; no new profile Mentor button

### Implementation for User Story 4

- [x] T024 [US4] Update Skill Points field in `apps/discord_bot/cogs/player_cog.py` (`build_player_profile`) for `overall >= potential` to show Mentor Ready + convertible MP/XP per `contracts/development-mentor-ui.md`
- [x] T025 [US4] Ensure non-maxed profile SP display stays the existing simple `**{sp}**` presentation; do not add a separate Mentor CTA button

**Checkpoint**: Quickstart §6 passes

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, docs, regression smoke

- [x] T026 [P] Update player-facing `change_log.md` with Mentor Transfusion (5 SP → 1 MP → 500 XP; 3/day; via `/development`)
- [x] T027 [P] Document mentor as SP→XP sink via `transfer_mentor_xp` → `apply_card_xp` in `AGENTS.md` and `.agents/AGENTS.md` (Section 7 progression — do not invent a second XP pipe)
- [x] T028 Reconcile Mentor Transfusion into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md`
- [x] T029 Run `pytest tests/test_mentor_math.py -q` and walk `specs/006-mentor-transfusion/quickstart.md` scenarios §1–§8 (including match/store/fusion regression smoke)
- [x] T030 [P] Persona walkthrough: double-tap confirm, match-lock block, injured source still allowed, stale skills embed; fix any clear UX gaps in `apps/discord_bot/cogs/development_cog.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP
- **US2 (Phase 4)**: Depends on US1 entry existing (polishes discovery)
- **US3 (Phase 5)**: Depends on US1 transfer handler; replaces MVP 1 MP-only confirm
- **US5 (Phase 6)**: Depends on US1 RPC path; cap already in SQL from Phase 2
- **US4 (Phase 7)**: Depends on Foundational math helpers only (can parallel with US3/US5 after Phase 2)
- **Polish (Phase 8)**: After desired stories complete

### User Story Dependencies

```text
Phase 2 Foundational
        ├── US1 (MVP transfer) ──┬── US2 (discovery polish)
        │                        ├── US3 (target/amount/preview)
        │                        └── US5 (daily pacing UX)
        └── US4 (profile Ready) [parallel after Phase 2]
```

- **US1**: No dependency on other stories
- **US2 / US3 / US5**: Build on US1 Development wiring
- **US4**: Independent of US2/US3/US5 after Foundational

### Parallel Opportunities

- T004 / T005 after T003 started (export + tests once API shape stable)
- T007 // T008 while T006 migration is authored (different files)
- US4 (T024–T025) // US3 or US5 after Foundational + US1
- T026 / T027 / T028 in Polish can run in parallel

---

## Parallel Example: Foundational

```bash
# After T003 mentor_math.py exists:
Task: "Export mentor helpers from packages/player_engine/player_engine/__init__.py"
Task: "Create tests/test_mentor_math.py"

# While writing migration T006:
Task: "scratch/apply_migration_052.py + verify_required_schema.sql"
Task: "Map mentor errors in apps/discord_bot/core/api_errors.py"
```

## Parallel Example: After US1

```bash
Task: "US4 profile Mentor Ready in apps/discord_bot/cogs/player_cog.py"
Task: "US3 amount buttons + preview in apps/discord_bot/cogs/development_cog.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundational (math + `052` + verify) — **CRITICAL**
3. Phase 3 US1 — minimal Mentor Transfer → target → 1 MP → RPC
4. **STOP and VALIDATE** on a test club (quickstart §1 at 1 MP)
5. Then US2 → US3 → US5 → US4 → Polish

### Incremental Delivery

1. Setup + Foundational → schema ready
2. US1 → first transferable MVP
3. US2 → discovery clarity
4. US3 → strategic amount/preview UX
5. US5 → pacing visibility
6. US4 → profile discoverability
7. Polish → changelog / AGENTS / SDD / quickstart sign-off

### Suggested MVP scope

**T001–T012** (Setup + Foundational + US1). Do not merge to production until migration verify passes and at least US2 discovery polish is in place so managers are not stuck on a hidden entry point.

---

## Notes

- [P] = different files, no incomplete-task dependencies
- No new slash commands or hub buttons beyond Development / profile extensions
- Never bypass `apply_card_xp`; never edit applied migrations in place
- Commit after each task or logical group when user requests commits
- Stop at any checkpoint to validate independently

# Tasks: Active Fatigue Recovery

**Input**: Design documents from `/specs/009-fatigue-recovery/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require extending `tests/test_fatigue_injury_math.py` (TG passive amounts, recovery-session clamp, hospital ignore TG). Discord/RPC paths validated via `quickstart.md`.

**Organization**: Tasks grouped by user story (US1–US4) for incremental delivery.

**Locked decisions** (from research.md R1–R8):
- Recovery Session is **instant** (no 4h job / no `player_drills` table) — reconcile FR-004
- New RPC `process_recovery_session` (do not overload `process_stat_drill`)
- +40 fatigue, 0 XP, 0 coins; energy = Basic drill (`fatigue_recovery_energy` default 10)
- Shares club (20) + per-card (5) daily drill caps via `daily_drill_count` / `player_drill_daily_log`
- Passive non-hospital = `15 + (training_ground_level × 5)`; hospital path unchanged (45)
- TG schema is 1–5 (TG0 unreachable); TG1 = 20 (legacy flat rate)
- Bench rest +15 unchanged; physio Store consumable out of scope
- Migration `054_fatigue_recovery.sql`; extend `/development` Training Drills only

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4
- Include exact file paths in descriptions

## Path Conventions

- Pure engine: `packages/player_engine/player_engine/`
- Bot: `apps/discord_bot/`
- SQL: `supabase/migrations/`, `supabase/scripts/verify_required_schema.sql`
- Tests: `tests/` at repo root
- Scratch: `scratch/`
- SDD: `.specify/specs/v1.0.0/`
- Feature docs: `specs/009-fatigue-recovery/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm contracts, call sites, and spec drift before code

- [x] T001 Reconcile FR-004 / acceptance copy in `specs/009-fatigue-recovery/spec.md` to **instant** Recovery (same completion UX as skill drills); note R1 in `specs/009-fatigue-recovery/research.md` if any further drift
- [x] T002 [P] Grep `apps/discord_bot/cogs/development_cog.py`, `apps/discord_bot/core/api_errors.py`, `apps/discord_bot/core/scheduler_jobs.py`, `packages/player_engine/player_engine/fatigue.py`, and `supabase/migrations/050_fatigue_injury_hospital.sql` for `process_stat_drill`, `process_daily_recovery`, `apply_passive_recovery`, `FATIGUE_PASSIVE`, `show_training_menu`, `StatDrillView`; list exact insertion points for Recovery UI, RPC, and TG passive

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure math + migration `054` (both RPCs + config) + verify + error mapping that all stories need

**⚠️ CRITICAL**: Do not ship Discord Recovery UI until migration `054` is applied and `verify_required_schema.sql` passes

- [x] T003 Extend `packages/player_engine/player_engine/fatigue.py` per `contracts/fatigue-recovery-math.md`: add `FATIGUE_PASSIVE_BASE`, `FATIGUE_PASSIVE_TG_PER_LEVEL`, `FATIGUE_RECOVERY_SESSION`; implement `passive_recovery_amount(tg_level)`, `apply_recovery_session`; update `apply_passive_recovery(..., tg_level=1)` (hospital path ignores TG); deprecate flat-only use of `FATIGUE_PASSIVE_PER_DAY` for non-hospital
- [x] T004 [P] Export new fatigue constants/helpers from `packages/player_engine/player_engine/__init__.py`
- [x] T005 [P] Extend `tests/test_fatigue_injury_math.py` for TG1→20, TG5→40, hospital ignores TG, `apply_recovery_session` clamp at 100, bench rest still +15
- [x] T006 Create `supabase/migrations/054_fatigue_recovery.sql` per `data-model.md`, `contracts/process-recovery-session-rpc.md`, and `contracts/daily-recovery-tg.md`: seed `game_config` (`fatigue_recovery_session`, `fatigue_recovery_energy`, `fatigue_passive_base`, `fatigue_passive_tg_per_level`); `CREATE OR REPLACE process_recovery_session`; `CREATE OR REPLACE process_daily_recovery` with TG join; GRANTs; migration-end schema guard for `function:process_recovery_session` (and existing daily recovery if needed)
- [x] T007 [P] Add `scratch/apply_migration_054.py` (follow existing scratch apply pattern) and extend `supabase/scripts/verify_required_schema.sql` for `function:process_recovery_session` (correct `split_part` for function entries)
- [x] T008 Map Recovery RPC exception fragments to manager-facing copy in `apps/discord_bot/core/api_errors.py` (`Player is already fully rested`, `Player is injured — use Hospital`; reuse existing daily-limit / energy strings where messages match)

**Checkpoint**: `pytest tests/test_fatigue_injury_math.py -q` green; migration applies; verify passes; no Discord Recovery button yet

---

## Phase 3: User Story 1 — Schedule a Recovery Session (Priority: P1) 🎯 MVP

**Goal**: Manager can run one Recovery Session from Development Training Drills and get fatigue back without XP

**Independent Test**: Fatigued non-injured card + energy + drill capacity → Recovery Session → fatigue +≤40 (cap 100), XP unchanged, energy/caps decremented; fully rested / injured reject cleanly

### Implementation for User Story 1

- [x] T009 [US1] Add Recovery Session confirm handler in `apps/discord_bot/cogs/development_cog.py` that: `defer`s immediately, calls `db.rpc("process_recovery_session", {p_owner_id, p_player_card_id})`, shows success (new fatigue / gained) or `api_error_message` failure embed
- [x] T010 [US1] Wire minimal entry from Training Drills player select → **Recovery Session** confirm → T009 handler in `apps/discord_bot/cogs/development_cog.py` (hardcode preview +40 / energy from config or defaults if preview helper not built yet)
- [x] T011 [US1] On success, show applied `fatigue_gained` / `new_fatigue` from RPC JSON; confirm XP/level fields are absent or zero in the success path in `apps/discord_bot/cogs/development_cog.py`
- [x] T012 [US1] Grep `apps/discord_bot/` to confirm Recovery path never calls `apply_card_xp`, never updates `players.coins` directly, and never bypasses `process_recovery_session` for fatigue writes

**Checkpoint**: One end-to-end Recovery Session works on a test club after migration apply (quickstart §1)

---

## Phase 4: User Story 2 — Choose Recovery vs Skill Development (Priority: P1)

**Goal**: Training Drills clearly presents Skill vs Recovery trade-off before commit; ineligible states explained

**Independent Test**: Open Training Drills for a fatigued eligible player — both Skill Drill and Recovery Session visible with distinct outcomes; evo/injured/full-fatigue cases message clearly

### Implementation for User Story 2

- [x] T013 [US2] Update `show_training_menu` embed copy in `apps/discord_bot/cogs/development_cog.py` per `contracts/development-recovery-ui.md`: mention Recovery Session (fatigue restore, 0 XP, energy, shares daily drill slots)
- [x] T014 [US2] After player select in `StatDrillView` (or adjacent short-lived view) in `apps/discord_bot/cogs/development_cog.py`, present explicit **Skill Drill** vs **Recovery Session** choice with outcome summary before commit
- [x] T015 [US2] Pre-disable or reject Recovery with clear copy when `fatigue >= 100`, injured/`in_hospital`, or active evo in `apps/discord_bot/cogs/development_cog.py` (RPC remains source of truth)
- [x] T016 [US2] Verify skill-drill path (`process_stat_drill`) still lists six drills and spends coins/XP unchanged in `apps/discord_bot/cogs/development_cog.py`

**Checkpoint**: Discovery UX matches FR-007 / quickstart §2–§5

---

## Phase 5: User Story 3 — Training Ground Speeds Passive Recovery (Priority: P2)

**Goal**: Daily passive fatigue scales with TG level; hospital path unchanged; bots benefit without UI

**Independent Test**: After `process_daily_recovery`, non-hospital cards gain `15 + TG×5`; hospital cards still use hospital daily amount; scheduler still calls the same RPC

### Implementation for User Story 3

- [x] T017 [US3] Confirm `supabase/migrations/054_fatigue_recovery.sql` `process_daily_recovery` body matches `contracts/daily-recovery-tg.md` (set-based `UPDATE … FROM players`, hospital branch untouched, injury discharge logic preserved from `050`)
- [x] T018 [US3] Grep callers of `apply_passive_recovery` / `FATIGUE_PASSIVE_PER_DAY` under `packages/` and `apps/`; update any preview/display math to pass `tg_level` (or use `passive_recovery_amount`) so UI does not advertise flat +20 when TG ≠ 1
- [x] T019 [US3] Confirm `apps/discord_bot/core/scheduler_jobs.py` `daily_recovery_job` still invokes `process_daily_recovery` with no signature change; no new APScheduler job
- [x] T020 [US3] Manually validate quickstart §6 (TG1 vs TG5 or before/after TG upgrade) against applied `054` DB

**Checkpoint**: FR-008 / FR-009 / SC-002 / SC-005 satisfied

---

## Phase 6: User Story 4 — Bench Rest Remains a Soft Lever (Priority: P3)

**Goal**: Competitive bench rest (+15) still applies; Recovery does not remove or replace it

**Independent Test**: Bench unused starter for a competitive match → +15 fatigue; can also use Recovery Session same day (cap 100)

### Implementation for User Story 4

- [x] T021 [US4] Grep `apps/discord_bot/` and `supabase/migrations/` for `apply_bench_rest` / `fatigue_bench` / bench recovery writes; confirm no change to +15 amount or competitive-only scope (friendlies remain sandbox)
- [x] T022 [US4] Smoke quickstart §7 regression: skill drill XP, match drain, Hospital admit path, mentor/fusion unchanged after Recovery ship

**Checkpoint**: FR-010 / FR-011 / FR-012 satisfied

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, docs, persona walkthrough

- [x] T023 [P] Update player-facing `change_log.md` with Recovery Session (+40 fatigue, 0 XP, energy + drill slot) and TG-scaled daily passive (`15 + TG×5`)
- [x] T024 [P] Document Recovery Session + TG passive under fatigue/US-39 notes in `AGENTS.md` and `.agents/AGENTS.md` (no second fatigue mutation pipe outside RPCs)
- [x] T025 Reconcile Active Fatigue Recovery into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` (extend US-39; instant Recovery; TG passive formula)
- [x] T026 Run `pytest tests/test_fatigue_injury_math.py -q` and walk `specs/009-fatigue-recovery/quickstart.md` scenarios §1–§7
- [x] T027 [P] Persona walkthrough: double-tap Recovery confirm, match-lock block, injured→Hospital copy, fully rested reject, exhausted drill caps, stale Training Drills embed; fix clear UX gaps in `apps/discord_bot/cogs/development_cog.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP
- **US2 (Phase 4)**: Depends on US1 entry existing (polishes discovery / choice)
- **US3 (Phase 5)**: Depends on Foundational migration (TG body already in `054`); validation + caller/display greps
- **US4 (Phase 6)**: Depends on Foundational; can run after US1 in parallel with US3
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

```text
Phase 2 Foundational (math + 054 + api_errors)
        ├── US1 (MVP Recovery Session) ── US2 (Skill vs Recovery choice UX)
        ├── US3 (TG passive validate/display) [parallel after Phase 2]
        └── US4 (bench regression) [parallel after Phase 2 / US1]
```

- **US1**: No dependency on other stories
- **US2**: Builds on US1 Training Drills wiring
- **US3 / US4**: Independent of each other after Foundational (US4 smoke happier after US1)

### Parallel Opportunities

- T004 / T005 after T003 API shape stable
- T007 // T008 while T006 migration is authored (different files)
- US3 (T017–T020) // US4 (T021–T022) after Phase 2
- T023 / T024 / T025 in Polish can run in parallel

---

## Parallel Example: Foundational

```bash
# After T003 fatigue.py helpers exist:
Task: "Export helpers from packages/player_engine/player_engine/__init__.py"
Task: "Extend tests/test_fatigue_injury_math.py"

# While writing migration T006:
Task: "scratch/apply_migration_054.py + verify_required_schema.sql"
Task: "Map recovery errors in apps/discord_bot/core/api_errors.py"
```

## Parallel Example: After Foundational

```bash
Task: "US3 validate TG process_daily_recovery + scheduler grep"
Task: "US1 Recovery Session handler in development_cog.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup (reconcile instant FR-004 + grep)
2. Phase 2 Foundational (math + `054` + verify) — **CRITICAL**
3. Phase 3 US1 — minimal Recovery Session → RPC
4. **STOP and VALIDATE** on a test club (quickstart §1)
5. Then US2 → US3 → US4 → Polish

### Incremental Delivery

1. Setup + Foundational → schema ready
2. US1 → Recovery works (MVP demo)
3. US2 → Choice UX clear
4. US3 → TG passive proven in daily job
5. US4 → Bench regression confirmed
6. Polish → changelog, AGENTS, v1.0.0 SDD, persona pass

### Suggested MVP Scope

**US1 only** (plus Foundational): managers can actively restore fatigue without benching. US2 is strongly recommended before public ship so Recovery is discoverable. US3 can ship in the same migration even if validation tasks lag slightly behind US1 UI.

---

## Notes

- [P] = different files, no incomplete-task dependencies
- Never add Store physio SKU or new slash commands in this feature
- Never call `apply_card_xp` from Recovery
- Apply `054` + verify before wiring bot UI that depends on the new RPC
- Commit after each task or logical group when the user requests commits

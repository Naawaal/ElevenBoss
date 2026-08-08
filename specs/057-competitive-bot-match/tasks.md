# Tasks: Competitive Bot Match Experience (NSS v3)

**Input**: Design documents from `/specs/057-competitive-bot-match/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — spec §30 and plan list engine/recovery/suspension/economy regression suites. Write failing tests before or with implementation per story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Engine: `packages/match_engine/`
- Bot: `apps/discord_bot/`
- Migrations: `supabase/migrations/`
- Tests: `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline docs + flag/config scaffolding without changing Bot Battle behavior

- [x] T001 Record current Bot Battle baseline notes (draw rate sample, typical stadium message cadence) in `specs/057-competitive-bot-match/quickstart.md` or a short `specs/057-competitive-bot-match/baseline-notes.md` for Phase 7–9 gates
- [x] T002 [P] Update `.specify/specs/v1.0.0/spec.md` US-12 to mention flag-gated competitive Bot Battle phases (ET/pens/suspensions) default OFF
- [x] T003 [P] Update `.specify/specs/v1.0.0/plan.md` Battle Arena section to point at Feature 057 NSS-stream extension (not a parallel engine)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration, flags, shared phase models, persistence helpers — MUST complete before any competitive stream behavior ships

**⚠️ CRITICAL**: No user-story stream changes until flag resolution + schema + `competitive_state` persistence primitives exist. Flag must default OFF so production Bot Battles stay baseline.

- [x] T004 Author `supabase/migrations/109_competitive_bot_match.sql`: `player_suspensions` table + RLS/policies; `match_runs.competitive_state` JSONB (or approved equivalent); optional `match_history.decided_by` / `home_penalties` / `away_penalties`; seed `game_config` keys from `data-model.md` with `competitive_match_enabled=false`; schema guard block
- [x] T005 Extend `supabase/scripts/verify_required_schema.sql` for `player_suspensions`, competitive settlement/list RPCs (as named in T004), and any new columns
- [x] T006 [P] Add `scratch/apply_migration_109.py` following `scratch/apply_migration_108.py` pattern
- [x] T007 [P] Implement pure phase/models module (e.g. `packages/match_engine/competitive_models.py`) with `MatchPhase`, score/phase snapshot helpers, and deterministic sub-seed derivation (`et1`/`et2`/`shootout` from `sim_seed`) — no Discord/DB
- [x] T008 Implement flag resolver `is_competitive_match_enabled()` (env `COMPETITIVE_MATCH_ENABLED` then `game_config.competitive_match_enabled`, default false) in `apps/discord_bot/core/` (e.g. `competitive_flags.py`) and wire a no-op read from `battle_cog.py` without changing match flow yet
- [x] T009 Add `match_runs` helpers to read/write `competitive_state` checkpoints in `apps/discord_bot/core/match_runs.py` (save phase, scores, seeds, penalty blob)

**Checkpoint**: Schema + flag + models ready; Bot Battle with flag off unchanged.

---

## Phase 3: User Story 1 - Extra Time After Drawn Regulation (Priority: P1) 🎯 MVP

**Goal**: Flag on + regulation draw → two 5-minute ET periods with carried fitness/discipline and elevated fatigue/injury multipliers; decisive ET completes without pens.

**Independent Test**: Flag off = baseline; flag on + tied 90' → ET1 then ET2; fitness not reset; ET goal ends match; `decided_by=extra_time` or regulation as appropriate.

### Tests for User Story 1

- [x] T010 [P] [US1] Add engine tests for draw→ET, ET completion, fatigue multiplier application, and same-seed determinism in `tests/test_competitive_extra_time.py`

### Implementation for User Story 1

- [x] T011 [US1] Extend NSS stream lifecycle in `packages/match_engine/v2_simulator.py` (and v3 wrappers under `packages/match_engine/v3/` as needed) so when competitive mode is requested and regulation is tied, stream continues EXTRA_TIME_FIRST (91–95) then EXTRA_TIME_SECOND (96–100) using existing interval/event generation
- [x] T012 [US1] Apply `competitive_extra_time_fatigue_multiplier` and `competitive_extra_time_injury_multiplier` from config during ET intervals without resetting fitness/discipline
- [x] T013 [US1] Emit high-signal phase events for ET start / ET break for the stadium adapter (engine events only — no Discord imports)
- [x] T014 [US1] Wire `execute_bot_battle` in `apps/discord_bot/cogs/battle_cog.py` to pass competitive mode when flag on, checkpoint `competitive_state` at ET boundaries via `match_runs.py`, and finalize with `decided_by=regulation|extra_time` when ET decides the match (still no shootout required for MVP demo if pens gated — prefer stubbing pens entry as incomplete until US2)
- [x] T015 [US1] Ensure `tests/test_competitive_economy_regression.py` (or extend existing bot reward tests) proves flag-off path and ET path do not double-settle XP/coins

**Checkpoint**: MVP — competitive ET works behind flag; production default still off.

---

## Phase 4: User Story 2 - Penalty Shootout After Extra-Time Draw (Priority: P2)

**Goal**: ET draw → deterministic pens (5 each, early stop, sudden death); football score unchanged; quality-based conversion.

**Independent Test**: ET draw enters pens; early mathematical win; sudden death; red-carded excluded; `3–3 (5–4 pens)` display fields populated.

### Tests for User Story 2

- [x] T016 [P] [US2] Add shootout unit tests (order, early stop, sudden death, eligibility, bounded P(goal), same seed) in `tests/test_penalty_shootout.py`

### Implementation for User Story 2

- [x] T017 [P] [US2] Implement `packages/match_engine/penalty_shootout.py` per `contracts/penalty-shootout.md` (derived composure/reflexes, ordering, kick resolve, serializable `PenaltyShootoutState`)
- [x] T018 [US2] Integrate shootout handoff from stream when EXTRA_TIME_SECOND ends tied; append kick events; never add pen goals to football score
- [x] T019 [US2] Persist `penalty_state` after each kick via `apps/discord_bot/core/match_runs.py`; set `decided_by=penalties` and pen tallies on completion
- [x] T020 [US2] Ensure settlement in `apps/discord_bot/core/match_rewards.py` does not grant XP for penalty kicks and keeps existing bot coin/XP pipes

**Checkpoint**: Full competitive arc ET→pens behind flag.

---

## Phase 5: User Story 3 - Restart-Safe Match Phases (Priority: P3)

**Goal**: Interrupted bot competitive matches resume mid-ET or mid-shootout without resimulating completed work.

**Independent Test**: Kill mid-ET / after 3 pens → recovery resumes next minute/kick only; double recovery no duplicate rewards/kicks.

### Tests for User Story 3

- [x] T021 [P] [US3] Add recovery tests (mid-ET, mid-pens, sudden death, idempotent double resume) in `tests/test_competitive_recovery.py`

### Implementation for User Story 3

- [x] T022 [US3] Incremental or phase-boundary `match_events` flush during competitive phases so recovery has durable history (extend battle stream flush path used today only at end)
- [x] T023 [US3] Extend `apps/discord_bot/core/match_recovery.py` to resume bot runs with valid `competitive_state` instead of abandon; keep abandon for unrestorable runs
- [x] T024 [US3] Wire resume entry from bot startup recovery into continuing `execute_bot_battle` / stadium handler without re-locking energy incorrectly (idempotent locks/settlement)

**Checkpoint**: Production-safe competitive matches under restart.

---

## Phase 6: User Story 4 - Red-Card Suspensions (Priority: P4)

**Goal**: Second-yellow → 1 Bot Battle ban; straight red → 2; block XI; atomic create/decrement on settlement.

**Independent Test**: Dismissal → row; `/battle bot` blocks card; after N completed Bot Battles, card eligible again.

### Tests for User Story 4

- [x] T025 [P] [US4] Add suspension create/decrement/eligibility tests in `tests/test_player_suspensions.py`

### Implementation for User Story 4

- [x] T026 [US4] Ensure live NSS stream emits dismissal consequences with `second_yellow` / `straight_red` and suspension lengths 1/2 (align with legacy metadata; extend `v2_simulator` card handling as needed)
- [x] T027 [US4] Implement atomic RPC(s) in migration 109 (or follow-up if already applied — prefer include in T004; else `110_…` only if 109 already shipped) `apply_bot_match_discipline` + `list_active_suspensions` per `contracts/suspensions-rpc.md`
- [x] T028 [US4] Call discipline RPC from `apps/discord_bot/core/match_rewards.py` / bot settlement once per run with dismissal payload
- [x] T029 [US4] Gate suspended cards in `apps/discord_bot/core/squad_validity.py` and `execute_bot_battle` XI checks with clear ephemeral messaging (no new command)

**Checkpoint**: Discipline has persistent Bot Battle weight.

---

## Phase 7: User Story 5 - Richer Events Without Stadium Spam (Priority: P5)

**Goal**: Fouls/FK/corners/offsides in stats; tiered commentary; ET/pen banners; shootout emoji sequence on one message.

**Independent Test**: Expanded stats present; Tier C not flooding Discord; shootout updates one embed; Tier A always surfaces.

### Tests for User Story 5

- [x] T030 [P] [US5] Add presenter/buffer unit tests (tier classification, shootout message update shape) under `tests/` (e.g. `tests/test_competitive_stadium_presentation.py`)

### Implementation for User Story 5

- [x] T031 [P] [US5] Extend NSS event generation/stats for foul, free kick, corner, offside (stats always; public timeline selective) in `packages/match_engine/v2_simulator.py` / related generators
- [x] T032 [P] [US5] Add commentary templates for ET/pen contexts in `packages/match_engine/commentary_bank.json` (and engine lookup)
- [x] T033 [US5] Implement stadium presentation buffer + phase banners + shootout emoji sequence in battle stadium handlers / embeds under `apps/discord_bot/` per `contracts/stadium-presentation.md`
- [x] T034 [US5] Surface extended stats and AET/pens final line in post-match embeds without new commands

**Checkpoint**: Readable competitive stadium.

---

## Phase 8: User Story 6 - Fair Dynamic Bot Difficulty (Priority: P6)

**Goal**: Bot strength tracks manager within configured deltas; same fatigue/cards/pen rules; no cheat bonuses.

**Independent Test**: Strength bands stay in bounds; reds/fatigue apply to AI; shootout uses shared model.

### Tests for User Story 6

- [x] T035 [P] [US6] Add difficulty bounding tests (delta clamps, no special pen bias) in `tests/test_competitive_bot_difficulty.py`

### Implementation for User Story 6

- [x] T036 [US6] Apply `bot_dynamic_difficulty_*` config when building AI squad in `apps/discord_bot/cogs/battle_cog.py` / `build_bot_match_squad` path — bound effective OVR/strength vs manager club
- [x] T037 [US6] Verify AI path shares discipline/fatigue/shootout code (no AI-only scoring branches); document in code comments only if a near-miss exists and remove it

**Checkpoint**: All six stories independently functional behind flag.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Calibration tooling, flag-off regression, changelog, soak gates

- [x] T038 [P] Add seeded batch calibration script or test under `scratch/` or `tests/` covering weak/equal/strong, high fatigue, multiple reds — report draw/ET/pen rates vs research targets
- [x] T039 Run full competitive test suite + flag-off Bot Battle regression (`pytest tests/test_competitive_*.py` and existing bot/match tests)
- [x] T040 Apply migration 109 on target DB; run `scratch/verify_schema_full.py` / `verify_required_schema.sql`
- [x] T041 Execute `specs/057-competitive-bot-match/quickstart.md` validation checklist (flag off/on, recovery, suspensions, cadence)
- [x] T042 [P] Add player-facing `change_log.md` section only when enabling for players (keep draft notes until controlled enable — do not claim live if flag still off)
- [x] T043 Confirm no new slash commands and no PvP resurfacing (grep gate for accidental imports)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all competitive behavior
- **US1 (Phase 3)**: Depends on Phase 2 — **MVP**
- **US2 (Phase 4)**: Depends on US1 stream phase machine
- **US3 (Phase 5)**: Depends on US1 persistence; strongly depends on US2 before claiming full shootout recovery (can stub ET-only recovery first)
- **US4 (Phase 6)**: Depends on Phase 2 schema; can parallelize after US1 if dismissals emit; full value after competitive matches produce reds
- **US5 (Phase 7)**: Depends on US1/US2 events existing; presentation can trail engine
- **US6 (Phase 8)**: Depends on Phase 2 config keys; can parallel with US5 after US1
- **Polish (Phase 9)**: After desired stories complete

### User Story Dependencies

```text
Phase 2
   └─ US1 (ET) ──┬── US2 (pens) ── US3 (full recovery)
                 ├── US3 (ET-only recovery early)
                 ├── US4 (suspensions)
                 ├── US5 (stadium/events)
                 └── US6 (AI difficulty)
```

### Parallel Opportunities

- T002/T003; T006/T007 after T004 started
- US2 tests T016 parallel with T017
- US4/US5/US6 can proceed in parallel after US1 MVP if staffed
- Polish T038/T042 parallel

---

## Parallel Example: User Story 1

```text
Task: T010 tests/test_competitive_extra_time.py
Task: T011 v2_simulator ET lifecycle
# then
Task: T012 fatigue/injury multipliers
Task: T014 battle_cog wiring + checkpoints
Task: T015 economy regression
```

## Parallel Example: After US1 MVP

```text
Dev A: US2 shootout (T016–T020)
Dev B: US4 suspensions (T025–T029)
Dev C: US5 presentation (T030–T034)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1–2 (109 + flag + models)  
2. Phase 3 US1 ET  
3. **STOP** — validate flag-off baseline + flag-on ET  
4. Do not enable flag in production  

### Incremental Delivery

1. US1 ET → US2 pens → US3 recovery (production gate)  
2. US4 suspensions → US5 stadium → US6 AI  
3. Calibration → controlled guild enable → default-on only after soak  

### Suggested Production Gates

- Before any guild enable: US1+US2+US3 green  
- Before default-on: US4–US6 + calibration + cadence soak  

---

## Notes

- Primary code path is NSS **v2/v3 stream**, not legacy `MatchSimulationResult` (research R1)
- Cite US-42 child on mutating PRs that touch match settlement/integrity
- Never invent parallel XP/coin pipes
- If T004 already applied when adding RPC late, ship `110_*` forward fix — do not edit applied 109 on remote
- Commit only when the user requests

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T003 | 3 |
| Foundational | T004–T009 | 6 |
| US1 Extra time | T010–T015 | 6 |
| US2 Shootout | T016–T020 | 5 |
| US3 Recovery | T021–T024 | 4 |
| US4 Suspensions | T025–T029 | 5 |
| US5 Stadium/events | T030–T034 | 5 |
| US6 AI difficulty | T035–T037 | 3 |
| Polish | T038–T043 | 6 |
| **Total** | T001–T043 | **43** |

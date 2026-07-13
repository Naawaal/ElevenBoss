# Tasks: Division-Tier Fatigue & Injury Rebalance

**Input**: Design documents from `/specs/016-tier-fatigue-rebalance/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pure-math unit tests listed in plan.md (`tests/test_tier_fatigue_rebalance.py`) — required by AGENTS verification for non-trivial formulas. No full Discord integration suite.

**Locked decisions** (research.md / specify clarify):
- 2-2-2 map: T1=Grassroots+Amateur, T2=Semi-Pro+Professional, T3=Elite+Legendary
- Persist `players.intensity_tier` (no `clubs` table); Monday weekly job writes it
- Soft-lock fillers deferred (FR-014); cup = forward-compat only (no cup code)
- Remove rating-gap `intensity` +5 surcharge; math lives in `player_engine` (not `match_engine/fatigue.py`)
- Migration: `061_tier_fatigue_rebalance.sql`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US7 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema/math work

- [x] T001 Grep `match_fatigue_drain`, `FATIGUE_BASE_DRAIN`, `BASE_RECOVERY_DAYS`, `fatigue_passive_base`, `process_daily_recovery`, `apply_match_fatigue`, `process_post_match_injuries`, `admit_to_hospital`, `backfill_injury_eta_fairness`, `intensity=`, `weekly_league_reset_job`, `hospital_panel_embed` callers; confirm touch list matches `specs/016-tier-fatigue-rebalance/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_061.py` from `scratch/apply_migration_060.py` (or latest) pattern — target `061_tier_fatigue_rebalance.sql` (no-op until migration exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Intensity map, pure math, migration RPCs, weekly tier write, match fitness wiring — **MUST complete before UI/story polish**

**⚠️ CRITICAL**: No Hospital/profile/battle UI or backfill invoke until this phase is done and schema verify + unit tests pass

- [x] T003 [P] Add `packages/player_engine/player_engine/intensity.py` per `contracts/intensity-tier-mapping.md` (`intensity_tier_for_division`, label helpers Low/Medium/High)
- [x] T004 [P] Retune `packages/player_engine/player_engine/fatigue.py` per `contracts/fatigue-drain-recovery-math.md`: tier drain bases 8/12/16, PHY×0.10, tactics +4/−2/0, remove `intensity` bool surcharge; `passive_recovery_amount(tg_level, *, intensity_tier)` = tier_base + TG×2
- [x] T005 [P] Retune `packages/player_engine/player_engine/injury_math.py` per `contracts/injury-hospital-math.md`: tier injury bases, fatigue_mod 0.0003, `recovery_days_for_intensity(severity, intensity_tier, hospital_level)` with sev 0.33/1.0/2.5; update fair ETA/overflow helpers to tier-aware model (retire flat `BASE_RECOVERY_DAYS` 1/4/7 as sole source)
- [x] T006 [P] Export new/changed helpers from `packages/player_engine/player_engine/__init__.py`
- [x] T007 [P] Add `tests/test_tier_fatigue_rebalance.py` covering: division→tier map; Tier1 PHY70 Neutral drain=1; Tier1 TG3 passive=41; Tier3 TG3 passive=21; Tier3 Moderate H5 days=4; injury base by tier; fair never-lengthen helper smoke
- [x] T008 Author `supabase/migrations/061_tier_fatigue_rebalance.sql`: `players.intensity_tier SMALLINT NOT NULL DEFAULT 1 CHECK (1..3)`; backfill from `division`; optional `game_config` JSON mirrors; schema guard block
- [x] T009 In `061_tier_fatigue_rebalance.sql`, `CREATE OR REPLACE` `process_daily_recovery` to use intensity_tier bases 35/25/15 + TG×2 (hospital +45 unchanged) per `contracts/fatigue-drain-recovery-math.md`
- [x] T010 In `061_tier_fatigue_rebalance.sql`, `CREATE OR REPLACE` `process_post_match_injuries` and `admit_to_hospital` recovery-day CASE to tier×severity÷H formula per `contracts/injury-hospital-math.md` (read club `intensity_tier` + `hospital_level`)
- [x] T011 In `061_tier_fatigue_rebalance.sql`, add `backfill_tier_fatigue_rebalance()` per `contracts/backfill-tier-fatigue-rpc.md` (hospital fair ETA, overflow fair remaining, uninjured fatigue floor ≥50, never lengthen, idempotent JSON summary)
- [x] T012 Extend `supabase/scripts/verify_required_schema.sql` with `column:players.intensity_tier` and `function:backfill_tier_fatigue_rebalance` (+ any replaced RPC guards if required by project pattern)
- [x] T013 Apply migration via `scratch/apply_migration_061.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green
- [x] T014 Update `apps/discord_bot/core/scheduler_jobs.py` `weekly_league_reset_job` to SET `intensity_tier` from settled `division` for all players after promo/relegation writes (drift-proof refresh)
- [x] T015 Update `apps/discord_bot/core/injury_rpc.py` `build_starter_drains` / `apply_post_match_fitness` to accept `intensity_tier`, pass into `match_fatigue_drain` and `select_post_match_injury` / `injury_chance`; remove `intensity: bool` parameter
- [x] T016 Update `apps/discord_bot/core/match_rewards.py` to load human `intensity_tier`, pass to fitness helpers, and **delete** rating-gap `intensity = opp_rating >= team_rating + 8` surcharge
- [x] T017 Update `apps/discord_bot/core/league_rewards.py` to load each human club’s `intensity_tier` and pass into `apply_post_match_fitness` (no shared forced tier across two humans)

**Checkpoint**: Schema verified; `pytest tests/test_tier_fatigue_rebalance.py -q` green; competitive match path uses tier drains without +5 surcharge; Monday job writes `intensity_tier`

---

## Phase 3: User Story 1 — Lower Divisions Feel Playable Daily (Priority: P1) 🎯 MVP

**Goal**: Grassroots/Amateur (Tier 1) managers get drain base 8 and daily recovery 35+TG×2 so a daily XI stays sustainable

**Independent Test**: Tier 1 club, Neutral, PHY 70 → drain 1; TG 3 daily tick → +41; one competitive match + daily recovery feels net-positive vs pre-patch base-18 world

### Implementation for User Story 1

- [x] T018 [US1] Ensure register / default path leaves new clubs at `intensity_tier = 1` (migration DEFAULT + any `register_player` insert in migrations/bot that lists columns explicitly includes or relies on DEFAULT) — grep `INSERT INTO.*players` / register RPC
- [x] T019 [US1] Smoke-validate Tier 1 path: document or assert in `tests/test_tier_fatigue_rebalance.py` the US1 acceptance anchors (drain 8 base table, passive 41 @ TG3) already covered; fix any remaining hardcoded `FATIGUE_BASE_DRAIN = 18` or `passive_recovery_amount` callers in `apps/discord_bot/` and `packages/`

**Checkpoint**: US1 math + wiring demoable for Grassroots without UI polish

---

## Phase 4: User Story 2 — Top Divisions Demand Rotation and Facilities (Priority: P1)

**Goal**: Elite/Legendary (Tier 3) use drain 16, passive 15+TG×2, injury base 0.60%, Moderate hospital base 8 with Hospital shortening (L5 → 4 days)

**Independent Test**: Tier 3 Moderate @ H5 → 4 days; Tier 3 TG3 passive → 21; drain base 16

### Implementation for User Story 2

- [x] T020 [P] [US2] Add/extend assertions in `tests/test_tier_fatigue_rebalance.py` for Tier 3 drain base 16, passive 21 @ TG3, Moderate H5 = 4, Major untreated H0 = 20
- [x] T021 [US2] Grep SQL/Python for leftover injury bases `1/4/7` or `WHEN 1 THEN 1` admit paths; confirm `061` replacements are the only live CASE for new admits (no dual formulas)

**Checkpoint**: Tier 3 hospital/injury math matches contracts for new admits and pure helpers

---

## Phase 5: User Story 3 — Mid-Ladder Intensity Is a Clear Step Up (Priority: P2)

**Goal**: Semi-Pro/Professional (Tier 2) use 12 / +25 / 0.40% / 5-day Moderate base; clear step between Amateur and Elite

**Independent Test**: Map Semi-Pro & Professional → tier 2; table values 12/25/0.40%/5; bases strictly 8→12→16

### Implementation for User Story 3

- [x] T022 [P] [US3] Extend `tests/test_tier_fatigue_rebalance.py` for Tier 2 map + table anchors and strict ordering of drain bases
- [x] T023 [US3] Confirm Monday promo Amateur→Semi-Pro updates `intensity_tier` 1→2 in `apps/discord_bot/core/scheduler_jobs.py` write path (no mid-week LP writer touches `intensity_tier`)

**Checkpoint**: 2-2-2 ladder complete in map + weekly writer

---

## Phase 6: User Story 4 — Hospital and Injury UI Transparency (Priority: P1)

**Goal**: Hospital panel shows intensity header; injured profile shows ETA + base/facility breakdown

**Independent Test**: Tier 3 Hospital shows High intensity + longer-base copy; Tier 1 does not; injured profile shows math breakdown; healthy profile does not

### Implementation for User Story 4

- [x] T024 [P] [US4] Update `apps/discord_bot/embeds/hospital_embeds.py` `hospital_panel_embed` per `contracts/hospital-profile-battle-ui.md` (intensity label from `intensity_tier` + division; Tier 3 longer-base warning)
- [x] T025 [US4] Ensure `apps/discord_bot/views/store_facilities.py` `show_hospital_panel` loads and passes `intensity_tier` (and division) into the embed
- [x] T026 [US4] Update `apps/discord_bot/embeds/profile_embeds.py` (and any injury summary helpers) to show severity, ETA, and `(Base: …d @ {tier/division} | Facility Bonus: −…%)` when injured per contract
- [x] T027 [US4] Confirm `/profile` hospital summary path in `apps/discord_bot/cogs/profile_cog.py` still uses shared ETA helpers and does not invent a second injury formula

**Checkpoint**: US4 independently demoable on Store Hospital + profile without matching

---

## Phase 7: User Story 5 — Pre-Match Fatigue Warning (Priority: P2)

**Goal**: Competitive pre-match ticket warns when any starter has fatigue &lt; 30 (count included); advisory only

**Independent Test**: 3 starters &lt; 30 → warning with count 3; all ≥ 30 → no warning; match still startable

### Implementation for User Story 5

- [x] T028 [US5] Locate competitive match ticket / pre-match embed builder used by `apps/discord_bot/cogs/battle_cog.py` (and shared embed module if any)
- [x] T029 [US5] Append advisory line when `sum(1 for s in starters if fatigue < 30) >= 1` per `contracts/hospital-profile-battle-ui.md`; skip friendlies/sandbox paths that do not persist fatigue

**Checkpoint**: Warning visible only when applicable; does not block start

---

## Phase 8: User Story 6 — Fair Migration (Priority: P1)

**Goal**: One-shot hospital ETA fair recalc + uninjured fatigue floor ≥50; never lengthen; idempotent

**Independent Test**: Far ETA shortens or early-discharges; fatigue 10 → ≥50 for uninjured; re-run no-op

### Implementation for User Story 6

- [x] T030 [US6] Invoke `backfill_tier_fatigue_rebalance` from `scratch/apply_migration_061.py` (or dedicated follow-up call) after DDL; log JSON summary
- [x] T031 [P] [US6] Optional: add `scratch/notify_tier_fatigue_backfill.py` (pattern from 057 notifier) to DM early discharges from RPC summary — best-effort, never rolls back data
- [x] T032 [US6] Add pure unit coverage for fair candidate/`LEAST`/early-clear and fatigue-floor eligibility rules in `tests/test_tier_fatigue_rebalance.py` (mirror SQL contract)

**Checkpoint**: Live/staging backfill run once; managers with open stays see fair ETAs; exhausted squads can play

---

## Phase 9: User Story 7 — Opponent AI Parity (Priority: P2)

**Goal**: Human vs bot matches use the human’s `intensity_tier` for injury probability on both sides in-sim; cup deferred (document only)

**Independent Test**: Tier 3 human vs bot → injury_chance / select path uses tier 3 bases for recorded rolls on both sides; fatigue persist still human-only

### Implementation for User Story 7

- [x] T033 [US7] Thread `intensity_tier` into `packages/match_engine/match_engine/v2_simulator.py` injury roll helpers (or call sites) so both sides use the human match owner’s tier for chance math per `contracts/match-ai-parity.md`
- [x] T034 [US7] Confirm league human-vs-human still uses each club’s own tier in `apps/discord_bot/core/league_rewards.py` (no cross-force)
- [x] T035 [US7] Add a one-line forward-compat note in `specs/016-tier-fatigue-rebalance/contracts/match-ai-parity.md` / plan only — **do not** implement cup fixtures

**Checkpoint**: Bot match injury intensity shares human tier params; no bot fatigue persistence invented

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, docs, and regression greps

- [x] T036 [P] Update `change_log.md` with player-facing tier intensity curve, UI transparency, and fair migration note (FR-015)
- [x] T037 [P] Reconcile `.specify/specs/v1.0.0/spec.md` (and `plan.md` if needed) for tiered fatigue/injury AC replacing global base-18 / 1-4-7-only language where this feature supersedes it
- [x] T038 Grep for dead `intensity=True`, `FATIGUE_BASE_DRAIN`, old tactic +8/−4, PHY 0.15, `BASE_RECOVERY_DAYS = {1: 1, 2: 4, 3: 7}` sole usage, and `fatigue_passive_tg_per_level = 5` in live drain/passive paths — fix or delete leftovers
- [x] T039 Run `pytest tests/test_tier_fatigue_rebalance.py tests/test_fatigue_injury_math.py -q` (update/skip obsolete 011 assertions that conflict with 016 numbers)
- [x] T040 Walk `specs/016-tier-fatigue-rebalance/quickstart.md` checklist manually (Hospital T1 vs T3, profile injury, pre-match warning, backfill idempotency)
- [x] T041 Confirm FR-014: no emergency grey/academy soft-lock code shipped; note monitor-only in changelog or spec Out of Scope if not already clear

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP math path
- **US2 (Phase 4)**: After Foundational — can parallel with US1 (tests mostly)
- **US3 (Phase 5)**: After Foundational — can parallel with US1/US2
- **US4 (Phase 6)**: After Foundational (needs `intensity_tier` on player payload)
- **US5 (Phase 7)**: After Foundational — parallel with US4
- **US6 (Phase 8)**: After Foundational T011+T013 (RPC exists + applied)
- **US7 (Phase 9)**: After Foundational T015–T017 (fitness helpers take tier)
- **Polish (Phase 10)**: After desired stories complete (recommend all P1 before polish)

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP |
| US2 | Phase 2 | Shares math with US1 |
| US3 | Phase 2 | Map + weekly writer |
| US4 | Phase 2 | UI only |
| US5 | Phase 2 | UI only |
| US6 | Phase 2 (backfill RPC) | Ops invoke |
| US7 | Phase 2 match wiring | Simulator thread |

### Parallel Opportunities

- T003–T007 (pure math + tests) in parallel after T001
- T024 // T028 once foundation done (different embed surfaces)
- T031 // T032 during US6
- US1–US3 test extensions largely parallel after T007

---

## Parallel Example: Foundational Math

```bash
# After T001–T002, launch in parallel:
Task: "Add intensity.py mapping helpers"
Task: "Retune fatigue.py drain/recovery"
Task: "Retune injury_math.py hospital/injury"
Task: "Add tests/test_tier_fatigue_rebalance.py"
```

## Parallel Example: UI Stories

```bash
# After Phase 2 checkpoint:
Task: "Hospital intensity header in hospital_embeds.py"
Task: "Pre-match fatigue warning in battle ticket embed"
```

---

## Implementation Strategy

### MVP First (US1 + Foundational)

1. Phase 1 Setup  
2. Phase 2 Foundational (math + `061` + match/weekly wiring)  
3. Phase 3 US1 smoke  
4. **STOP and VALIDATE**: Tier 1 drain/passive + schema verify + unit tests  
5. Then US2/US6 (P1 hospital curve + fair backfill) before soft UI (US4/US5)

### Suggested ship order

1. Foundational + US1 + US2 + US6 (balance + fairness)  
2. US4 + US5 (transparency)  
3. US3 + US7 (ladder completeness + AI parity)  
4. Polish (changelog, SDD, greps, quickstart)

### MVP scope

**Minimum demo**: Phase 1–3 (Setup + Foundational + US1).  
**Minimum production ship**: add US2 + US6 (Tier 3 curve + fair backfill) + T036 changelog.  
**Full feature**: all phases through T041.

---

## Notes

- Do **not** implement soft-lock fillers or cup competitions
- Do **not** invent `packages/match_engine/fatigue.py`
- Do **not** UPDATE `player_cards.fatigue` outside fatigue RPCs / backfill RPC
- Commit after each logical group if user requests commits; otherwise leave working tree for `/speckit.implement`
- Stop at any checkpoint to validate independently

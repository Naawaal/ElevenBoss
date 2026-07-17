# Tasks: League Dynamics Overhaul

**Input**: Design documents from `/specs/020-league-dynamics/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pure-math unit tests from plan (`tests/test_league_dynamics_windows.py`, `tests/test_seasonal_promo_relegation.py`, `tests/test_momd_selection.py`) — required by AGENTS for non-trivial window/promo/MoMD formulas. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Flag `league_dynamics_enabled` default **false**; season `pacing_mode` `legacy`|`dynamics` set at start only
- Dynamics: **14 days**, **8 clubs/tier**, double RR → 14 matchdays; UTC midnight hard close; tick ~**00:05 UTC**
- Split when humans **> 8**; bot-fill each tier to 8; top/bottom **2** promo/releg → `league_members.seasonal_division_tier`
- MoMD: **manual human wins only**; 2000 coins (`league_momd_coins`); one award/(season, matchday); Journal only
- Weekly Division Rank **untouched**; no new slash commands
- Migration: `064_league_dynamics.sql`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema work

- [x] T001 Grep `auto_sim_expired_fixtures`, `update_current_matchday`, `admin_start_season`, `distribute_season_prizes`, `window_end`, `compute_promotions_relegations`, `generate_round_robin_fixtures` callers; confirm touch list matches `specs/020-league-dynamics/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_064.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure helpers, schema, RPCs — **MUST complete before Dynamics season start / tick / MoMD UX**

**⚠️ CRITICAL**: No admin Dynamics start, scheduler cron tick, or MoMD Journal wiring until this phase is done and schema verify passes

- [x] T003 [P] Implement `packages/leagues/leagues/dynamics_windows.py` per `contracts/daily-tick-windows.md`: `assign_dynamics_windows(start_time, total_matchdays)` → per-matchday `window_start`/`window_end` (UTC midnight ends)
- [x] T004 [P] Implement `packages/leagues/leagues/seasonal_divisions.py` per `contracts/division-seating-promo.md`: `seat_humans_into_divisions`, `compute_fixed_promo_relegation` (fixed top/bottom 2; n&lt;4 skip; **do not** reuse weekly 20% `compute_promotions_relegations`)
- [x] T005 [P] Implement `packages/leagues/leagues/momd.py` per `contracts/manager-of-the-matchday.md`: `select_momd_winner` (manual human wins only; margin → GF → club_id)
- [x] T006 [P] Export new helpers from `packages/leagues/leagues/__init__.py`
- [x] T007 [P] Add `tests/test_league_dynamics_windows.py` covering MD1 mid-day start, midnight alignment, 14 matchdays
- [x] T008 [P] Add `tests/test_seasonal_promo_relegation.py` covering 8-human seating chunks, overflow to Div2, fixed-2 promo, n&lt;4 no-op
- [x] T009 [P] Add `tests/test_momd_selection.py` covering eligible pick, auto-sim exclusion, draw/AI exclusion, deterministic ties, empty → None
- [x] T010 Author `supabase/migrations/064_league_dynamics.sql` per `data-model.md`: alter `league_seasons` add `pacing_mode` (`legacy`|`dynamics`, default/backfill `legacy`); alter `league_participants` add `division_tier` DEFAULT 1 + index `(season_id, division_tier)`; alter `league_fixtures` add `resolved_by` NULL|`manual`|`auto_sim`; alter `league_members` add `seasonal_division_tier` DEFAULT 1; create `league_matchday_manager_awards` + UNIQUE `(season_id, matchday)` + indexes + RLS; seed `game_config` keys (`league_dynamics_enabled` false, `league_momd_coins` 2000, clubs_per_div 8, promo_spots 2, default_duration 14); optional `league_dynamics_enabled()` helper; schema guard block
- [x] T011 In `064_league_dynamics.sql`, implement `award_manager_of_the_matchday(p_season_id, p_matchday)` per `contracts/manager-of-the-matchday.md` (`apply_club_economy` source `league_momd`, key `momd:{season}:{matchday}`, statuses awarded/already_awarded/no_eligible/pending)
- [x] T012 In `064_league_dynamics.sql`, implement `apply_seasonal_promotion_relegation(p_season_id)` per `contracts/division-seating-promo.md` (Dynamics only; update `league_members.seasonal_division_tier`; idempotent guard)
- [x] T013 In `064_league_dynamics.sql`, replace/extend `distribute_season_prizes(p_season_id)` to pay **per `division_tier`** (humans-only standings within tier; meta includes tier); call promo/releg after prizes (or document bot calls promo RPC immediately after)
- [x] T014 Extend `supabase/scripts/verify_required_schema.sql` with columns/table/RPCs/policies/config from 064 (correct `split_part` for functions/policies)
- [x] T015 Apply migration via `scratch/apply_migration_064.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green

**Checkpoint**: Schema verified; `pytest tests/test_league_dynamics_windows.py tests/test_seasonal_promo_relegation.py tests/test_momd_selection.py -q` green; bot wiring can begin

---

## Phase 3: User Story 1 — Daily Matchday Tick (Priority: P1) 🎯 MVP

**Goal**: Dynamics seasons use UTC midnight hard closes; ~00:05 UTC tick auto-sims expired fixtures; legacy keeps 10-min interval

**Independent Test**: Dynamics season fixtures share midnight `window_end`; after close, cron tick sims unplayed and advances matchday; hub shows 00:00 UTC deadline; legacy seasons still polled by interval job only

### Implementation for User Story 1

- [x] T016 [US1] Add bot helper to read `league_dynamics_enabled` (e.g. in `apps/discord_bot/core/economy_rpc.py` or `apps/discord_bot/core/league_rewards.py` beside existing `get_game_config` patterns)
- [x] T017 [US1] Branch `admin_start_season` fixture window assignment in `apps/discord_bot/cogs/admin_cog.py`: when Dynamics, use `assign_dynamics_windows` from package; set `pacing_mode='dynamics'`; else keep rolling windows + `pacing_mode='legacy'`
- [x] T018 [US1] Set `resolved_by='auto_sim'` when auto-sim path completes in `apps/discord_bot/cogs/league_cog.py` / `apps/discord_bot/cogs/battle_cog.py` `run_league_match_simulation` (null/`active_player_id` absence path — coordinate so auto-sim writes the column)
- [x] T019 [US1] Filter `auto_sim_expired_fixtures_job` in `apps/discord_bot/core/scheduler_jobs.py` to seasons with `pacing_mode='legacy'` (NULL treated as legacy)
- [x] T020 [US1] Add `dynamics_daily_tick_job` in `apps/discord_bot/core/scheduler_jobs.py` (and optional thin `apps/discord_bot/tasks/` module) that auto-sims **only** `pacing_mode='dynamics'` active seasons, then triggers matchday settlement / Journal notify
- [x] T021 [US1] Register cron **00:05 UTC** Dynamics tick in `apps/discord_bot/main.py` beside `daily_recovery_job`
- [x] T022 [US1] Hub / fixtures countdown copy in `apps/discord_bot/cogs/league_cog.py` per `contracts/league-hub-copy.md` for Dynamics midnight UTC deadline

**Checkpoint**: US1 demoable — midnight windows + tick without needing multi-division or MoMD

---

## Phase 4: User Story 2 — Two-Week Seasons (Priority: P1)

**Goal**: Dynamics starts force 14-day / 14-matchday 8-club tables; announcements state the cadence

**Independent Test**: Flag on → admin start yields `duration_days=14`, `total_matchdays=14`, one 8-club table when ≤8 humans; announcement mentions 14-day + daily midnight

### Implementation for User Story 2

- [x] T023 [US2] In `apps/discord_bot/cogs/admin_cog.py` Dynamics start path: force `duration_days=14`, ignore oversized max_clubs / 10–16 size ladder for Dynamics; document constraint in admin success embed (D15)
- [x] T024 [P] [US2] Update `SeasonConfigModal` / registration defaults in `apps/discord_bot/cogs/admin_cog.py` when flag on: duration default **14** (legacy path keeps 28 when flag off)
- [x] T025 [US2] Update `apps/discord_bot/core/league_announcement.py` (and start message build site) for Dynamics: 14-day season + daily 00:00 UTC close + auto-sim after midnight

**Checkpoint**: US2 independently visible on next Dynamics season start (builds on US1 windows)

---

## Phase 5: User Story 5 — Safe Rollout for Living Seasons (Priority: P1)

**Goal**: Flag default off; active seasons stay legacy; ops can pilot Dynamics without rewriting in-flight competitions

**Independent Test**: After migration, existing active season has `pacing_mode='legacy'` and unchanged windows; flag off → new starts still legacy; flag on → only new starts Dynamics

### Implementation for User Story 5

- [x] T026 [US5] Confirm `admin_start_season` / registration paths respect flag: flag off never sets `dynamics` even if code paths shared (`apps/discord_bot/cogs/admin_cog.py`)
- [x] T027 [P] [US5] Add `scratch/smoke_league_dynamics.py` covering: legacy season untouched filter; Dynamics window sample; optional MoMD RPC idempotent re-call
- [x] T028 [US5] Grep scheduler + auto-sim to ensure Dynamics seasons are not double-processed by both interval and cron in a harmful way (interval must skip dynamics)

**Checkpoint**: SC-006 / rollout story satisfied before enabling flag in production

---

## Phase 6: User Story 3 — Guild Division Pyramid (Priority: P2)

**Goal**: >8 humans → multi-tier seating; standings by tier; season-end top/bottom 2 promo/releg; per-tier prizes

**Independent Test**: 9 humans → Div1 + Div2 (8 each with bots); hub shows viewer’s Division N; season complete updates `league_members.seasonal_division_tier` correctly

### Implementation for User Story 3

- [x] T029 [US3] Dynamics seating in `apps/discord_bot/cogs/admin_cog.py`: order humans via `league_members.seasonal_division_tier`; `seat_humans_into_divisions`; create AI fill per tier; insert `league_participants` with `division_tier`; generate **intra-tier** round-robin fixtures only; charge fees safely if humans skipped
- [x] T030 [US3] Extend `fetch_standings` in `apps/discord_bot/cogs/league_cog.py` to filter by `division_tier` (default viewer’s tier); hub standings show “Division N” label per `contracts/league-hub-copy.md`
- [x] T031 [US3] Wire season-complete path (`update_current_matchday` / `admin_end_season` in `apps/discord_bot/cogs/league_cog.py` and `apps/discord_bot/cogs/admin_cog.py`) so per-tier `distribute_season_prizes` + `apply_seasonal_promotion_relegation` run for Dynamics seasons
- [x] T032 [P] [US3] Journal / standings posts in `apps/discord_bot/core/league_journal.py`: when multiple tiers, post or section tables per division without merging ranks
- [x] T033 [US3] Disambiguate Weekly Rank vs seasonal Division labels anywhere hub shows both (grep `division` in `apps/discord_bot/cogs/league_cog.py` / profile peers if league rank appears)

**Checkpoint**: Multi-division Dynamics season seatable and promo-ready; weekly ladder still separate

---

## Phase 7: User Story 4 — Manager of the Matchday (Priority: P2)

**Goal**: After each fully settled matchday, one MoMD (manual human win) gets coins + Journal line; all-auto-sim → skip

**Independent Test**: Manual blowout wins MoMD over auto-sim; re-settle no double pay; all-sim MD → no award / no Journal MoMD

### Implementation for User Story 4

- [x] T034 [US4] Set `resolved_by='manual'` on human-initiated league match completion in `apps/discord_bot/cogs/battle_cog.py` (play path with `active_player_id`)
- [x] T035 [US4] After matchday fully resolved, call `award_manager_of_the_matchday` from settlement path in `apps/discord_bot/cogs/league_cog.py` (from `update_current_matchday` / post-auto-sim / last manual completer — exactly once per MD via RPC idempotency)
- [x] T036 [US4] Post Journal MoMD line on `status='awarded'` in `apps/discord_bot/core/league_journal.py` (or caller) per `contracts/league-hub-copy.md`; never spam MatchDay thread
- [x] T037 [P] [US4] Mention MoMD rules in Dynamics season-start announcement via `apps/discord_bot/core/league_announcement.py`
- [x] T038 [US4] Map MoMD RPC errors to friendly ephemerals if surfaced in `apps/discord_bot/core/api_errors.py` (only if call sites can fail user-visible)

**Checkpoint**: MoMD demoable on a Dynamics matchday; economy pipe + idempotent keys only

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene across stories

- [x] T039 [P] Update `change_log.md` with player-facing League Dynamics notes (midnight deadline, 14-day seasons, divisions, MoMD) for when flag is enabled
- [x] T040 [P] Reconcile `.specify/specs/v1.0.0/league-mode-design.md` pacing section (48h / 4–6 weeks → Dynamics defaults) without deleting weekly-ladder decoupling rule
- [x] T041 Run `specs/020-league-dynamics/quickstart.md` validation checklist (pytest + schema verify + flag off/on smoke)
- [x] T042 Grep confirm zero writes from league fixtures into `players.league_points` / weekly ladder; confirm no new slash commands added

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP tick/windows
- **US2 (Phase 4)**: After US1 window branch exists (shares `admin_cog` Dynamics path)
- **US5 (Phase 5)**: After US1 scheduler split (validates grandfathering); can overlap end of US2
- **US3 (Phase 6)**: After US1+US2 Dynamics start path (extends seating)
- **US4 (Phase 7)**: After Foundational MoMD RPC + US1 settlement path; ideally after `resolved_by` auto-sim (T018) and manual (T034)
- **Polish (Phase 8)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Daily Tick | Foundation | MVP |
| US2 Two-Week | US1 Dynamics branch in admin | Forces 14d on same path |
| US5 Rollout | US1 scheduler filter | Flag/grandfather proof |
| US3 Divisions | US1+US2 start path | Seating + prizes + promo |
| US4 MoMD | Foundation + settlement + `resolved_by` | Can start after T018; needs T034 |

### Parallel Opportunities

- T003–T009 pure modules/tests in parallel after T001
- T007–T009 tests parallel once helpers exist (or TDD: tests first then green)
- T024 / T027 / T032 / T037 / T039 / T040 marked [P] where files differ
- US3 and US4 mostly sequential on settlement/`league_cog` — avoid parallel edits to same functions

### Parallel Example: Foundational helpers

```bash
# After T001, launch pure packages in parallel:
Task: "dynamics_windows.py"
Task: "seasonal_divisions.py"
Task: "momd.py"
# Then tests in parallel:
Task: "test_league_dynamics_windows.py"
Task: "test_seasonal_promo_relegation.py"
Task: "test_momd_selection.py"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup  
2. Phase 2 Foundational (migration + pure math)  
3. Phase 3 US1 Daily Tick  
4. **STOP** — validate midnight windows + 00:05 tick on a test guild with flag on and ≤8 humans (single tier ok without US3)

### Incremental Delivery

1. Setup + Foundational → schema green  
2. US1 → daily tick MVP  
3. US2 → 14-day forced defaults  
4. US5 → rollout confidence / smoke  
5. US3 → multi-division pyramid  
6. US4 → MoMD engagement layer  
7. Polish → changelog + SDD + quickstart

### Suggested MVP scope

**US1 + Foundation** (optional US2 for correct 14-day defaults in same PR if small). Divisions and MoMD ship as follow-on increments behind the same flag.

---

## Notes

- [P] = different files, no incomplete dependencies
- Do **not** reuse `compute_promotions_relegations` for seasonal tiers
- Do **not** merge weekly Division Rank with seasonal `division_tier`
- Commit after each task or logical group when implementing
- Stop at checkpoints to validate independently
- `/speckit.implement` starts at T001

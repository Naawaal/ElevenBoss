# Tasks: League Automation & Config

**Input**: Design documents from `/specs/021-league-automation-and-config/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md  
**Depends on**: 020 League Dynamics (migration 064 + Dynamics seating/tick/MoMD) shipped/available

**Tests**: Include pure unit tests from plan (`tests/test_league_automation_rules.py`) — Monday reopen, min humans, open eligibility. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Reuse `guild_config.league_channel_id` + `announcement_role_id` (no `guilds` table)
- Flag `league_automation_enabled` default **false**; optional per-guild override NULL=inherit
- Single job `league_state_machine_job` **00:05 UTC**; **fold** `dynamics_daily_tick_job` into it
- Registration **48h**; under-min → Monday 00:05 reopen; min = `league_min_humans`
- Automation-owned seasons: `config_json.automation=true`; always Dynamics start path
- `/admin` when automation on: **Pause / Force End** only (hide Open/Start)
- Migration: `065_league_automation.sql`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema work

- [x] T001 Grep `admin_open_registration`, `admin_start_season`, `dynamics_daily_tick_job`, `auto_sim_expired_fixtures`, `league_channel_id`, `announcement_role_id`, `LeagueManagementView` callers; confirm touch list matches `specs/021-league-automation-and-config/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_065.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure rules, schema, shared start extract, announce helpers — **MUST complete before state-machine wiring**

**⚠️ CRITICAL**: No live automation job or admin Open/Start gating until this phase is done and schema verify passes

- [x] T003 [P] Implement `packages/leagues/leagues/automation.py` per `contracts/registration-windows.md`: `next_monday_0005_utc`, `registration_closes_at`, `can_open_auto_registration`, `evaluate_registration_close`, `automation_effective(global, guild_flag)`
- [x] T004 [P] Export automation helpers from `packages/leagues/leagues/__init__.py`
- [x] T005 [P] Add `tests/test_league_automation_rules.py` covering Monday 00:05 edges, 48h close, under-min vs start, `can_open` with `next_auto_registration_at`, effective-flag truth table
- [x] T006 Author `supabase/migrations/065_league_automation.sql` per `data-model.md`: alter `guild_config` add `league_automation_enabled BOOLEAN NULL`, `next_auto_registration_at TIMESTAMPTZ NULL`, `automation_last_error TEXT NULL`; seed `league_automation_enabled` false + `league_automation_registration_hours` 48; helper `league_automation_enabled()`; schema guard block
- [x] T007 Extend `supabase/scripts/verify_required_schema.sql` with 065 columns/functions (correct `split_part`)
- [x] T008 Apply migration via `scratch/apply_migration_065.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green
- [x] T009 [P] Add `apps/discord_bot/core/economy_rpc.py` helpers: `league_automation_enabled(db)`, `guild_automation_effective(db, guild_id)` (global ∧ per-guild inherit)
- [x] T010 Extract shared `start_dynamics_season_from_registration(...)` from `apps/discord_bot/cogs/admin_cog.py` (or into `apps/discord_bot/core/league_automation.py`) — Dynamics seating/windows/threads from 020 path; accept `automation: bool` to set `config_json.automation` / `pacing_mode='dynamics'`; leave `admin_start_season` as thin wrapper when automation off
- [x] T011 [P] Implement announce helpers in `apps/discord_bot/core/league_announce.py` (or extend `league_announcement.py`) per `contracts/announce-digests.md`: registration open/fail, season start, daily tick digest, season conclusion — role ping via `announcement_role_id`; swallow send errors + set `automation_last_error`

**Checkpoint**: Schema verified; `pytest tests/test_league_automation_rules.py -q` green; shared start + announce helpers callable

---

## Phase 3: User Story 1 — Configure announce channel & role once (Priority: P1)

**Goal**: `/admin` clearly labels league announce channel / mention role; shows automation last error; no new settings store

**Independent Test**: Set channel + role in `/admin`; labels read as League announce / mention; broken channel shows error hint when set

### Implementation for User Story 1

- [x] T012 [US1] Update Announcement Settings + Admin Hub copy in `apps/discord_bot/cogs/admin_cog.py` to “League announce channel” / “League mention role” per `contracts/admin-automation-gates.md`
- [x] T013 [US1] Surface `automation_last_error` on admin hub embed in `apps/discord_bot/cogs/admin_cog.py` when present; clear on successful channel send from job later

**Checkpoint**: US1 demoable without enabling automation job

---

## Phase 4: User Story 5 — Safe rollout / flags (Priority: P1)

**Goal**: Flag default off; grandfather unmarked seasons; per-guild inherit works

**Independent Test**: Flag off → no auto open; enabling flag does not rewrite active manual season windows

### Implementation for User Story 5

- [x] T014 [US5] Confirm flag-off short-circuits in orchestrator entry (`apps/discord_bot/core/league_automation.py`) before any open/start
- [x] T015 [P] [US5] Add `scratch/smoke_league_automation.py`: print effective flag, `next_monday_0005_utc` sample, list automation-owned registration seasons (read-only)

**Checkpoint**: SC-004 path safe before enabling job behaviors in production

---

## Phase 5: User Story 2 — Autonomous season cycle (Priority: P1) 🎯 MVP

**Goal**: Job opens 48h registration, closes → start or Monday fail-path, conclude → reopen; admin Open/Start gated

**Independent Test**: Pilot guild + flag on + channel → registration announce → (with ≥min humans) Dynamics start without admin Start; under-min → Monday cooldown

### Implementation for User Story 2

- [x] T016 [US2] Implement open-registration + close/start/fail flows in `apps/discord_bot/core/league_automation.py` per `contracts/league-state-machine.md` phases B–C (ownership `config_json.automation`, `registration_closes_at`, under-min → `next_auto_registration_at`)
- [x] T017 [US2] After automation-owned season complete (detect from tick/`update_current_matchday`), same-run open next registration when channel OK (SC-003)
- [x] T018 [US2] Gate `LeagueManagementView` in `apps/discord_bot/cogs/admin_cog.py`: when automation effective, hide/disable Open Registration + Start Season; keep Pause + Force End; footer explaining automation
- [x] T019 [US2] Wire `league_state_machine_job` registration/start branches in `apps/discord_bot/core/scheduler_jobs.py` calling orchestrator
- [x] T020 [US2] Registration announce + under-min + season-start announce via `league_announce` helpers; block auto-open if channel missing (set `automation_last_error`)

**Checkpoint**: Registration→start (or Monday fail) demoable; admin cannot double-start

---

## Phase 6: User Story 3 — Daily tick digest (Priority: P1)

**Goal**: Fold Dynamics tick into state machine; announce digest after settlement; idempotent `last_digest_matchday`

**Independent Test**: Unplayed fixture past midnight → 00:05 sims + MoMD rules + announce digest once; retry no duplicate digest

### Implementation for User Story 3

- [x] T021 [US3] In `league_state_machine_job` / orchestrator: for all active `pacing_mode='dynamics'` seasons, run auto_sim → `update_current_matchday` (pass bot) per contract phase A
- [x] T022 [US3] Post daily tick digest when automation effective + channel OK + completed matchday &gt; `last_digest_matchday`; update `config_json.last_digest_matchday`
- [x] T023 [US3] Remove `dynamics_daily_tick_job` registration from `apps/discord_bot/main.py`; register `league_state_machine_job` cron **00:05 UTC** only (keep legacy 10-min interval for `pacing_mode=legacy`)
- [x] T024 [US3] Confirm `/league` hub Dynamics midnight deadline copy still correct in `apps/discord_bot/cogs/league_cog.py` (no regression); show automated registration close time when `status=registration` + `registration_closes_at` present

**Checkpoint**: One 00:05 job; no double-sim; digest + hub deadline OK

---

## Phase 7: User Story 4 — Managers via `/league` only (Priority: P2)

**Goal**: Register/play unchanged; no new slash commands; hub explains automated registration when open

**Independent Test**: Register via hub during auto registration; play before midnight; inventory confirms no new player slash

### Implementation for User Story 4

- [x] T025 [US4] Hub registration UX in `apps/discord_bot/cogs/league_cog.py`: when automated registration open, show close countdown; remove “ask admin to start” as the only CTA when automation owns the season
- [x] T026 [US4] Grep `apps/discord_bot` for new `@app_commands.command` added by this feature — assert none; document lifecycle stays job + `/admin` emergency only

**Checkpoint**: Player surface unchanged aside from hub copy

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene

- [x] T027 [P] Update `change_log.md` with player-facing autonomous league notes (flagged; announce pings; midnight play; Monday retry if not enough managers)
- [x] T028 [P] Reconcile `.specify/specs/v1.0.0/league-mode-design.md` with autonomous ops note (admin sets channel/role once)
- [x] T029 Run `specs/021-league-automation-and-config/quickstart.md` checklist (pytest + schema + flag off/on smoke)
- [x] T030 Grep confirm: no `dynamics_daily_tick_job` still scheduled; no writes to `players.league_points` from automation path; Journal MoMD still single-pay (announce is mirror)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all stories
- **US1 (Phase 3)**: After Foundational announce/admin copy helpers
- **US5 (Phase 4)**: After flag helpers (T009) — can overlap US1
- **US2 (Phase 5)**: After Foundational start extract + US1 channel labels — MVP lifecycle
- **US3 (Phase 6)**: After US2 orchestrator skeleton (shares job)
- **US4 (Phase 7)**: After US2 registration exists (hub copy)
- **Polish (Phase 8)**: After desired stories

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Config labels | Foundation T011–T012 | |
| US5 Rollout | Foundation T009 | Flag short-circuit |
| US2 Cycle 🎯 | Foundation T010 + US1 channel | MVP |
| US3 Tick digest | US2 job wired | Folds Dynamics tick |
| US4 Hub | US2 registration | Copy only |

### Parallel Opportunities

- T003–T005 pure/tests after T001
- T009 / T011 in parallel with T010 (different files) carefully
- T027 / T028 polish docs in parallel
- Avoid parallel edits to `admin_cog.py` / `main.py` / orchestrator

### Parallel Example: Foundation

```bash
Task: "packages/leagues/leagues/automation.py"
Task: "tests/test_league_automation_rules.py"
Task: "scratch/apply_migration_065.py"
```

---

## Implementation Strategy

### MVP First (US2 + Foundation + US1 gates)

1. Phase 1–2 Foundation  
2. US1 labels + US5 flag short-circuit  
3. US2 open/close/start + admin gates + job registration/start  
4. **STOP** — validate one pilot registration→start  

### Incremental Delivery

1. Foundation → schema green  
2. US1 + US5 → safe config  
3. US2 → autonomous cycle MVP  
4. US3 → tick fold + digests  
5. US4 → hub polish  
6. Polish → changelog + quickstart  

### Suggested MVP scope

**Foundation + US1 + US5 + US2**. Ship US3 digests/tick fold in the same PR if small (required to remove duplicate 00:05 Dynamics job safely — do not leave both jobs registered).

---

## Notes

- [P] = different files, no incomplete dependencies  
- Do **not** invent `guilds.league_announce_*` columns  
- Do **not** leave `dynamics_daily_tick_job` and state machine both simming Dynamics  
- `/speckit.implement` starts at T001  

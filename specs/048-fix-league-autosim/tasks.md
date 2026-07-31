# Tasks: Fix League Expired Auto-Sim Pending Forever

**Input**: Design documents from `/specs/048-fix-league-autosim/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart call for `tests/test_league_expired_settle.py` (decision matrix) plus reuse `tests/test_double_forfeit_standings.py`; Discord/SQL smoke on Season #2 MD5. No full integration suite.

**Locked decisions** (research.md / plan.md):
- Root cause: `run_league_match_simulation` silently skips when `human_club_xi_ok` fails; `auto_sim_expired_fixtures` never settles
- Post-window fallback: **026** `single_forfeit` (3–0) / `double_forfeit` (0–0) via `packages/leagues/leagues/forfeit_rules.py`
- Wire via new `apps/discord_bot/core/league_expired_settle.py`; do **not** weaken live Play XI gate
- Threads missing + eligible XI → silent sim; guild unreachable → pause/skip, **no** sporting forfeit
- No migration expected; cite **US-42.5**
- **Note (implement)**: `resolved_by` CHECK only allows `manual`|`auto_sim` — forfeit writes use `auto_sim` + `result_type`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US3 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and column availability (no migration unless gap found)

- [x] T001 Grep `auto_sim_expired_fixtures`, `human_club_xi_ok`, `Pending Auto-Sim`, `single_forfeit`, `run_league_match_simulation`, and `skip_xi_gate` across `apps/discord_bot/` and `packages/leagues/`; confirm touch list matches `specs/048-fix-league-autosim/plan.md`
- [x] T002 [P] Confirm `league_fixtures` already has `result_type`, `resolved_by`, `status`, `played_at` (read lifecycle forfeit writes in `apps/discord_bot/core/league_lifecycle_engine.py` ~583–612); only file a migration if a column is missing

**Checkpoint**: Touch list known; no unnecessary migration planned

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure settle decision + reusable forfeit write helper — **MUST land before wiring auto-sim loop**

**⚠️ CRITICAL**: Keep Discord out of `packages/`; pure decision only in packages if extracted

- [x] T003 Add pure decide helper `(home_ok, away_ok) → sim | forfeit_home | forfeit_away | double_forfeit` in `packages/leagues/leagues/expired_settle.py` (or colocated pure function in `apps/discord_bot/core/league_expired_settle.py` if staying app-only); export from `packages/leagues/leagues/__init__.py` if package path chosen
- [x] T004 [P] Add `tests/test_league_expired_settle.py` covering decision matrix (TT→sim, FT→forfeit home illegal, TF→forfeit away illegal, FF→double) and expected `single_forfeit`/`double_forfeit` scorelines; assert AI-always-legal is documented in helper contract
- [x] T005 Create `apps/discord_bot/core/league_expired_settle.py` with `settle_expired_fixture(...)`: re-check `is_played` + active `match_runs`; evaluate `human_club_xi_ok` (AI = ok); on forfeit modes write fixture like lifecycle (`is_played`, scores, `status='forfeit'`, `result_type`, `resolved_by='auto_sim'`, `played_at`) settle-once; on sim call existing path; **no** match XP/coins on forfeit per `contracts/expired-fixture-settle.md`

**Checkpoint**: Decision + forfeit write testable without Discord; foundation ready for US1 wiring

---

## Phase 3: User Story 1 — Expired fixtures finish so the matchday can move on (Priority: P1) 🎯 MVP

**Goal**: Every expired unplayed fixture settles via auto-sim **or** 026 forfeit; matchday can advance

**Independent Test**: Legacy active season with expired unplayed fixture (incl. past-grace human XI) → hub open or job → `is_played=true` with score/forfeit; when all MD fixtures played, `update_current_matchday` advances

**Contract**: [contracts/expired-fixture-settle.md](./contracts/expired-fixture-settle.md)

### Implementation for User Story 1

- [x] T006 [US1] Refactor `auto_sim_expired_fixtures` in `apps/discord_bot/cogs/league_cog.py` to call `settle_expired_fixture` per expired unplayed fixture instead of blind `run_league_match_simulation` that silent-skips on XI failure
- [x] T007 [US1] In settle/sim path: when guild OK but season threads missing, use silent handler (mirror `league_lifecycle_engine._resolve_fixture`) so eligible fixtures still settle; keep guild-unreachable → existing pause/skip (**no** forfeit)
- [x] T008 [US1] Preserve skip-while-active `match_runs` and ensure `update_current_matchday` still runs at end of `auto_sim_expired_fixtures` after successful settles
- [x] T009 [US1] Confirm `apps/discord_bot/core/scheduler_jobs.py` `auto_sim_expired_fixtures_job` still invokes the updated `auto_sim_expired_fixtures` (no duplicate legacy path); hub-on-open callers (~590/608) unchanged aside from shared function behavior
- [x] T010 [US1] SQL/Discord smoke from `quickstart.md`: Season #2 MD5 pending fixtures (`d641b016-…`, `c8f1eb10-…` or current IDs) settle within one cycle; re-open hub → scores unchanged (settle-once)

**Checkpoint**: US1 MVP — pending fixtures resolve; matchday can advance

---

## Phase 4: User Story 2 — Honest hub copy when settle is blocked or delayed (Priority: P2)

**Goal**: Fixtures show Forfeit / Double Forfeit (or actionable pending hint), not perpetual Pending with no next step

**Independent Test**: After forfeit settle, Fixtures shows score + Forfeit label; if still unplayed with known eligibility block, copy names club/reason or clears on next cycle

**Contract**: [contracts/fixtures-pending-copy.md](./contracts/fixtures-pending-copy.md)

### Implementation for User Story 2

- [x] T011 [US2] Update Fixtures status rendering in `apps/discord_bot/cogs/league_cog.py` (~835): played + `result_type=forfeit` → `(Forfeit)`; `double_forfeit` → `(Double Forfeit)`; normal played keep Full Time
- [x] T012 [P] [US2] Best-effort: expired unplayed + human eligibility fail → append short renew/replace XI hint from `club_xi_block_reason` (or club name) so Pending is not the only line after a settle cycle
- [x] T013 [P] [US2] Extend `tests/test_league_expired_settle.py` (or small pure copy helper test) for forfeit label mapping if display helper is extracted; otherwise document expected strings in test comments tied to Fixtures branch

**Checkpoint**: US2 — managers can tell forfeit vs Full Time vs pending-with-hint

---

## Phase 5: User Story 3 — Silent failures are visible to ops and recoverable (Priority: P3)

**Goal**: Infra failures fail closed and retry; mid-sim cleanup retained so later settle works

**Independent Test**: Documented: guild/threads back → next hub/job settles; active-run abandon path still clears blockers

### Implementation for User Story 3

- [x] T014 [US3] Verify/ harden: guild unreachable still returns early / pauses without marking fixtures played in `auto_sim_expired_fixtures` / settle helper (`apps/discord_bot/cogs/league_cog.py`, `apps/discord_bot/core/league_expired_settle.py`)
- [x] T015 [US3] On mid-sim exception in settle path, retain abandon of active `match_runs` (existing battle_cog / lifecycle pattern) so a later cycle can proceed; log fixture id + reason at warning level
- [x] T016 [P] [US3] Ensure `specs/048-fix-league-autosim/quickstart.md` integrity checks stay accurate (no mass forfeit on guild leave; past-grace → forfeit not infinite Pending)

**Checkpoint**: US3 — outage ≠ forfeit; retry recovers

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene

- [x] T017 [P] Add player-facing note to `change_log.md`: expired league fixtures resolve after the window; illegal XI (e.g. expired contracts) → forfeit 3–0 / double forfeit, not stuck Pending
- [x] T018 Run `pytest tests/test_league_expired_settle.py tests/test_double_forfeit_standings.py -q` and mark quickstart Discord smoke complete
- [x] T019 Confirm no new slash commands/tables; grep confirms live Play still uses XI gate (forfeit only on **post-window** settle); cite US-42.5 in any PR blurb

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** US1 wiring
- **US1 (Phase 3)**: After Foundational (settle helper exists)
- **US2 (Phase 4)**: After US1 settle writes `result_type` (UI can start in parallel once forfeit writes land)
- **US3 (Phase 5)**: After US1 settle path exists (harden skip/abandon)
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Fixtures settle | Phase 2 | MVP hotfix |
| US2 Honest Fixtures copy | US1 forfeit writes | Labels need `result_type` |
| US3 Infra recoverable | US1 settle path | Absence≠outage |

### Parallel Opportunities

- T002 with T001
- T004 tests while T003/T005 written
- T011/T012 UI while T010 smoke prep
- T016 / T017 during smoke

---

## Parallel Example: Foundational

```text
Task: "Add pure decide helper (packages or core)"
Task: "Add tests/test_league_expired_settle.py"
Task: "Create league_expired_settle.py forfeit write + sim branch"
```

---

## Parallel Example: User Story 1

```text
Task: "Wire auto_sim_expired_fixtures to settle helper"
Task: "Silent sim when threads missing; preserve matchday advance"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Decision + `league_expired_settle`  
3. Phase 3 Wire `auto_sim_expired_fixtures` + Season #2 smoke  
4. **STOP and VALIDATE**: MD5 pending pair settled; matchday advances  
5. Deploy bot

### Incremental Delivery

1. Foundational decide/forfeit → unit green  
2. US1 wire auto-sim → production hole closed  
3. US2 Fixtures forfeit labels  
4. US3 infra harden + changelog  

### Suggested MVP scope

**Phases 1–3 (US1)**: settle helper + auto-sim wire + smoke. Enough to unstick Season #2 Matchday 5.

---

## Notes

- [P] = different files or safely parallel
- Do **not** set `skip_xi_gate=True` for live Play; forfeit only after `window_end`
- Prefer no migration; lifecycle forfeit column pattern already exists
- Commit after each phase checkpoint when implementing
- Stop at US1 checkpoint to unblock production if needed

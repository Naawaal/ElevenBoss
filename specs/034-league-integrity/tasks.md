# Tasks: League Integrity (US-42.5)

**Input**: Design documents from `/specs/034-league-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: `032`, `033`, `026`, `027`

**Tests**: Required — `tests/test_league_integrity_pause.py` (+ prize/ops greps). Migration **078** only if W1 decides RPC is needed (default: Python-only).

**Locked decisions** (research.md / league-integrity-audit.md):
- `026`/`027` own sporting rules — no second calendar
- All pause paths MUST set `pause_started_at`; widen open-status filter
- Keep `_run_once` / prize economy keys / `promo_applied` — lock with tests
- Absence = assistant (`026`); outage = pause (no invented forfeits)
- Leave guild = no club delete; AI prizes humans-only
- Fix paused Play copy (no Discord admin resume)
- Prefer Python fixes; **078** optional

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`…`[US5]` maps to spec user stories

---

## Phase 1: Setup — W0 audit confirm

**Purpose**: Re-confirm Critical gaps before patching

- [x] T001 Re-confirm `specs/034-league-integrity/contracts/league-integrity-audit.md` against `apps/discord_bot/core/guild_resolver.py` (pause without `pause_started_at`; status filter) and paused Play copy in `apps/discord_bot/cogs/battle_cog.py` / `league_cog.py`
- [x] T002 [P] Note Critical ordered fix list in `specs/034-league-integrity/checklists/requirements.md` Notes
- [x] T003 [P] Confirm next migration is `078` only if RPC chosen; default path = no new migration

**Checkpoint**: Audit current; no code yet

---

## Phase 2: Foundational — Shared pause helper (preferred)

**Purpose**: One write path for pause so all callers set metadata correctly

- [x] T004 Add shared helper e.g. `pause_league_season(db, season_id, *, reason: str)` in `apps/discord_bot/core/league_lifecycle_engine.py` (or `guild_resolver.py`) that sets `status=paused` + `pause_started_at` (preserve existing `pause_started_at` if already paused) for open non-terminal statuses per `contracts/pause-resume.md`
- [x] T005 [P] Define `OPEN_PAUSEABLE_STATUSES` constant (include `active`, `registration_open`, `registration_locked`, `preparing`, legacy `registration` if still queried)

**Checkpoint**: Single pause writer ready

---

## Phase 3: User Story 2 — Outage pauses correctly (Priority: P1) 🎯 MVP

**Goal**: Unreachable / bot-remove pause sets rebase clock; no invented forfeits

**Independent Test**: SC-002 / SC-003 class

### Tests

- [x] T006 [P] [US2] Create `tests/test_league_integrity_pause.py`: source assert pause helpers write `pause_started_at`; status filter includes V1 open statuses; no mass-forfeit on pause path

### Implementation

- [x] T007 [US2] Wire `pause_season_if_guild_unreachable` in `apps/discord_bot/core/guild_resolver.py` through shared pause helper (fix omit `pause_started_at` + narrow `.in_("status", …)`)
- [x] T008 [US2] Wire `pause_seasons_for_guild` / `on_guild_remove` path to same helper
- [x] T009 [P] [US2] Align `pause_season` in `league_lifecycle_engine.py` with helper (extend beyond `active` only if Soft gap warrants — at least keep `pause_started_at`)
- [x] T010 [P] [US2] Confirm resume still requires `pause_started_at` and rebases windows — no behavior change if metadata now present

**Checkpoint**: Pause MVP

---

## Phase 4: User Story 1 — Transitions / prizes once (Priority: P1)

**Goal**: Double catch-up / prize settle idempotent (lock existing mechanisms)

**Independent Test**: SC-001

### Tests

- [x] T011 [P] [US1] In `tests/test_league_integrity_pause.py` (or `tests/test_league_integrity_idempotency.py`): assert `_run_once` / `acquire_operation` unique-key pattern present in `league_lifecycle_engine.py`
- [x] T012 [P] [US1] Grep/assert `season_prize:` economy key + `ON CONFLICT` awards + `promo_applied` / `already_applied` in latest `distribute_season_prizes` / `apply_seasonal_promotion_relegation` migration source
- [x] T013 [P] [US1] Assert deadline resolve skips `is_played` fixtures in `league_lifecycle_engine.py`

### Implementation

- [x] T014 [US1] Fix any Critical hole found by T012–T013 only (do not redesign prize RPC if keys already correct)
- [x] T015 [P] [US1] Skip optional **078** unless pause helper cannot be trusted from Python alone — if added: `pause_league_season` RPC + verify guards + scratch apply/smoke

**Checkpoint**: Idempotency locked by tests

---

## Phase 5: User Story 3 — Absence / Play vs deadline (Priority: P1)

**Goal**: Assistant absence path untouched; Play respects pause + already-played

### Implementation

- [x] T016 [US3] Replace “Wait for admin to resume” paused Play copy in `apps/discord_bot/cogs/battle_cog.py` (and any twin in `league_cog.py`) with ops/server-available wording per `027`
- [x] T017 [P] [US3] Confirm human Play still blocked when `status == paused` (existing gate); clear ephemeral reason
- [x] T018 [P] [US3] Spot-check deadline path does not invent forfeits from pause — forfeit only via existing illegal-XI engine (`026`)

**Checkpoint**: Absence vs outage UX correct

---

## Phase 6: User Story 4 — Seats / leave-guild / AI (Priority: P2)

**Goal**: INV-12 / INV-15 regression coverage

### Tests

- [x] T019 [P] [US4] Assert `distribute_season_prizes` humans-only (`is_ai = FALSE`) in SQL source
- [x] T020 [P] [US4] Grep `apps/discord_bot` for member-leave / guild-leave handlers that delete `players` or wipe cards — expect **zero** hard deletes
- [x] T021 [P] [US4] Cite US-42.3 soft Abandoned register Block still enforced (076 / existing tests) — no rewrite

### Implementation

- [x] T022 [P] [US4] Soft only: if leave-guild continuity message is one-liner and already gated, skip; else optional ephemeral note — default **skip** (YAGNI)

**Checkpoint**: Seat/AI bounds documented + grepped

---

## Phase 7: User Story 5 — Coherent manager story (Priority: P2)

**Goal**: Stale Play / pause messaging consistent

### Implementation

- [x] T023 [P] [US5] Already-played Play path still fails closed (existing) — add source assert if missing
- [x] T024 [P] [US5] No new slash commands / no Discord pause admin UI restored

**Checkpoint**: UX integrity intact

---

## Phase 8: Polish & Cross-Cutting

- [x] T025 [P] Run `pytest tests/test_league_integrity_pause.py -q` (+ idempotency file if split)
- [x] T026 [P] Update `change_log.md` with pause/resume integrity note (managers see new paused copy)
- [x] T027 Run `quickstart.md` Validations 0–5 as applicable; set `specs/034-league-integrity/spec.md` Status → Locked
- [x] T028 Confirm zero calendar rewrite / no `026` sport rule changes / no marketplace/economy-registry work; grep cleanup
- [x] T029 [P] Pointer in `.specify/specs/v1.0.0/spec.md` (near league/US-42) to `specs/034-league-integrity` (US-42.5)
- [x] T030 [P] Mark all tasks complete in this file when implement finishes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: Immediate
- **Phase 2**: Before US2 wire-up (T004–T005)
- **Phase 3 US2**: MVP Critical pause — first code
- **Phase 4 US1**: Tests anytime after audit; fixes only if holes
- **Phase 5 US3**: After pause works (copy + gates)
- **Phase 6–7**: Parallel with Phase 4 tests
- **Phase 8**: After US2 + US3 minimum

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US2 | Phase 2 | Pause metadata Critical |
| US1 | Audit | Mostly tests |
| US3 | US2 | Copy + gates |
| US4 | — | Greps |
| US5 | US3 | Messaging |

### Parallel Opportunities

- T001 then T002 || T003
- T006 || T011 || T012 || T013 once pause API stable
- T019 || T020 || T021 in Phase 6
- T026 || T029 in Polish

### MVP stop

After T007–T010 + T016 (pause metadata + copy) even if prize greps still drafting — then finish T011–T013 before Lock.

---

## Implementation Strategy

1. Phase 1 audit confirm  
2. Phase 2 shared pause helper  
3. Phase 3 wire unreachable / guild-remove (US2)  
4. Phase 5 paused Play copy (US3)  
5. Phase 4/6 tests + changelog + Lock  

### Suggested stop points

| Stop | When |
|------|------|
| Pause MVP | After T010 |
| Copy + tests | After T016 + T013 |
| Full child | After T030 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Same-file `guild_resolver` / `league_lifecycle_engine` tasks = sequential
- Soft outbox / leave UX deferred unless one-liner
- Commit only when user requests

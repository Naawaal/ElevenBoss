# Tasks: Club State Machine (US-42.3)

**Input**: Design documents from `/specs/032-club-state-machine/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: US-42.1 (`030` / migration `074`) | **Overlays**: `026`/`027` (sport), `031` (cards separate)

**Tests**: Required — `tests/test_club_state_matrix.py`, `tests/test_club_state_sql_guards.py` (+ smoke after 076).

**Locked decisions** (research.md):
- Reuse US-42.1 soft columns/RPCs — **no** second `club_status` column
- Pure `packages/player_engine/club_state.py` + SQL `assert_club_action_allowed` in **`076_club_state_guards.sql`**
- Atomic **`register_league_season`** replaces cog-only V1 join inserts (Critical gap)
- LeagueSeated = overlay; Inactive/Abandoned Block **new** league join only; no mid-season kick
- AI via `players.is_ai`; classify skips AI (074)
- No new slash commands; no XP/economy pipe rewrite; no `026` calendar rewrite; no `031` card matrix rewrite

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`…`[US5]` maps to spec user stories

---

## Phase 1: Setup — W0 club path audit

**Purpose**: Confirm Critical gap (league cog join) and migration number before coding

- [x] T001 Confirm/fill `specs/032-club-state-machine/contracts/club-rpc-guard-audit.md` against `apps/discord_bot/cogs/league_cog.py` `player_register_league` (no soft Active gate today) and note legacy `league_members`-only branch
- [x] T002 [P] Record Critical gap ordered list in `specs/032-club-state-machine/checklists/requirements.md` Notes: (1) V1 seasonal join → RPC, (2) legacy join branch if still live
- [x] T003 [P] Confirm next migration is `076` (no `076_*.sql` yet) and touch list matches `specs/032-club-state-machine/plan.md` Structure

**Checkpoint**: Gap list ready; no code yet

---

## Phase 2: Foundational — Pure club state module 🎯 MVP core

**Purpose**: Readable SoT for soft lifecycle + kind + overlays + `can_perform_club_action` matching §B.5

**⚠️ CRITICAL**: Matrix tests and hub reason mapping depend on this module

- [x] T004 Create `packages/player_engine/player_engine/club_state.py` per `contracts/club-state-derive.md`: `ClubKind`, soft lifecycle helpers (reuse `identity.classify_status` / 30–90 defaults), `derive_overlays`, `can_perform_club_action`
- [x] T005 Implement matrix outcomes in `club_state.py` per `contracts/club-action-matrix.md` and spec §B.5 (`league_join` Block when Inactive/Abandoned; store/dev/squad Allow when soft; MatchLocked blocks mutations; AI blocks human hub + join + store)
- [x] T006 Export new symbols from `packages/player_engine/player_engine/__init__.py`

**Checkpoint**: Pure module importable

---

## Phase 3: User Story 1 — Soft lifecycle explicit & recoverable (Priority: P1) 🎯 MVP

**Goal**: Soft Active/Inactive/Abandoned teachable; recovery same club; no second register

**Independent Test**: SC-001/002 — thresholds + recover; register still ALREADY_REGISTERED

### Tests

- [x] T007 [P] [US1] Create or extend tests covering soft classify via `club_state` / `identity` at day 29/30/90; AI skip soft labels; recover path semantics documented (RPC already in 074 — assert pure mirrors)

### Implementation

- [x] T008 [US1] Document in `club_state.py` that durable classify/recover/touch remain 074 RPCs; pure module does not invent parallel storage
- [x] T009 [P] [US1] Confirm `recover_club_identity` / `classify_club_identity_status` still skip or no-op AI as in 074 — no weakening

**Checkpoint**: Soft lifecycle MVP aligned with 074

---

## Phase 4: User Story 2 — Club matrix + SQL assert (Priority: P1)

**Goal**: Shared SQL assert encodes club matrix; pure tests cover key cells

**Independent Test**: Matrix tests + `assert_club_action_allowed` in 076

### Tests

- [x] T010 [P] [US2] Create `tests/test_club_state_matrix.py`: ≥10 parameterized cells (Inactive×league_join Block, Abandoned×league_join Block, Inactive×store_faucet Allow, Inactive×development_mutate Allow, Active×league_join Allow, AI×league_join Block, MatchLocked×match_start Block, MatchLocked×view_hub Allow, Abandoned×recover Allow, Active×view_hub Allow)

### Implementation

- [x] T011 [US2] Create `supabase/migrations/076_club_state_guards.sql`: `assert_club_action_allowed(p_club_id BIGINT, p_action TEXT)` per `contracts/sql-assert-club-action.md` (lock club, AI gates, soft classify or read status, MatchLocked via `assert_not_in_match` for mutations, `CLUB_STATE:` raises); GRANT + migration DO guard
- [x] T012 [P] [US2] Extend `supabase/scripts/verify_required_schema.sql` for `assert_club_action_allowed` (+ `register_league_season` when added in T013)
- [x] T013 [P] [US2] Create `tests/test_club_state_sql_guards.py`: migration contains `assert_club_action_allowed`, `CLUB_STATE`, and `register_league_season`

**Checkpoint**: Assert defined; matrix tests green

---

## Phase 5: User Story 3 — League seat bounds / atomic join (Priority: P1)

**Goal**: Server-enforced seasonal join; Active-only new registration; idempotent AlreadySeated; no calendar rewrite

**Independent Test**: SC-003/004 — Inactive/Abandoned join Block; leave guild does not delete club (existing 030)

### Implementation

- [x] T014 [US3] In `076_club_state_guards.sql` add `register_league_season(p_player_id, p_guild_id, p_season_id, …)` per `contracts/register-league-season.md`: call assert `league_join`, validate open season for guild, ensure `league_members`, upsert `league_registrations`, `touch_club_activity`, return AlreadySeated JSON when duplicate
- [x] T015 [US3] Prefer re-check min career matches / account age inside RPC (fail-closed) using same config sources as cog where practical
- [x] T016 [US3] Create `apps/discord_bot/core/club_rpc.py` thin wrappers (`assert` optional, `register_league_season`, reuse identity recover/classify if helpful)
- [x] T017 [US3] Wire `apps/discord_bot/cogs/league_cog.py` `player_register_league` V1 path to call `register_league_season` RPC instead of raw upserts; map `CLUB_STATE:` / errors to ephemeral embeds; keep defer
- [x] T018 [P] [US3] Legacy permanent `league_members`-only join branch: call assert/`register` helper or shared Active gate — do not leave ungated soft join
- [x] T019 [P] [US3] Confirm UNIQUE `(season_id, player_id)` on `league_registrations` still present (070) — document in checklist Notes; no weakening

**Checkpoint**: Join path server-enforced

---

## Phase 6: User Story 4 — AI clubs bounded (Priority: P2)

**Goal**: AI kind never human-register; soft classify skip; join Block

**Independent Test**: SC-005

### Tests

- [x] T020 [P] [US4] Extend `tests/test_club_state_matrix.py`: AI × league_join / store_faucet / development_mutate Block

### Implementation

- [x] T021 [US4] Ensure SQL assert AI branch matches pure matrix; `register_league_season` rejects `is_ai`
- [x] T022 [P] [US4] Do **not** rewrite `league_automation` bot fill — only confirm it still sets `is_ai` (checklist note)

**Checkpoint**: INV-15 bound at join/assert

---

## Phase 7: User Story 5 — Qualifying activity teachable (Priority: P2)

**Goal**: Join success touches activity; views do not; thresholds documented

### Implementation

- [x] T023 [US5] `register_league_season` success path calls `touch_club_activity` (074)
- [x] T024 [P] [US5] Confirm view-only league/profile paths do not call touch; economy touch path from 074 remains
- [x] T025 [P] [US5] Keep 30/90 defaults in sync between `identity.py` and SQL classify/assert (constants or shared comment)

**Checkpoint**: Activity rules consistent

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Apply, verify, docs, lock

- [x] T026 Add `scratch/apply_migration_076.py` and `scratch/smoke_club_state_076.py` (functions exist; Inactive/Abandoned league_join Block if fixture available)
- [x] T027 Apply `076` when `DATABASE_URL` set; run smoke; note skip if unavailable
- [x] T028 [P] Run `pytest tests/test_club_state_matrix.py tests/test_club_state_sql_guards.py -q`
- [x] T029 [P] Update `change_log.md` with soft-status / league join gate player-facing notes
- [x] T030 [P] Optional: profile soft-status badge — **skip** unless already trivial; gates must work without UI
- [x] T031 Run `specs/032-club-state-machine/quickstart.md` Validations 0–4 as applicable; set `spec.md` Status → Locked
- [x] T032 Confirm zero new slash commands / no economy-XP pipe edits / no second status column / no `026` calendar edits / no `031` card matrix edits; grep cleanup
- [x] T033 [P] Pointer in `.specify/specs/v1.0.0/spec.md` (e.g. near league or US-22) to `specs/032-club-state-machine` (US-42.3)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Audit**: Immediate — informs T014–T018
- **Phase 2 Pure module**: Blocks quality of US2 tests
- **Phase 3 US1**: After T004–T006 (mostly documentation + reuse 074)
- **Phase 4 US2**: Assert in 076
- **Phase 5 US3**: After T011 assert exists; Critical delivery
- **Phase 6–7 US4/US5**: After assert + join RPC drafted
- **Phase 8 Polish**: After US2+US3 minimum

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 + 074 | Soft reuse |
| US2 | Phase 2 + 076 assert | Matrix |
| US3 | US2 assert | Join RPC + cog |
| US4 | US2 assert | AI |
| US5 | US3 join | Touch on join |

### Parallel Opportunities

- T001 then T002 || T003
- T007 || T010 || T020 once pure API stable
- T012 || T013 after T011 written
- T018 || T019 after T017 planned
- T029 || T030 || T033 in Polish

### Parallel Example: After `club_state.py` exists

```text
Task: T007 soft/threshold tests
Task: T010 tests/test_club_state_matrix.py
Task: T011 start 076 assert SQL
```

---

## Implementation Strategy

### MVP First (US1 + US2 assert + US3 join)

1. Phase 1 audit  
2. Phase 2–4 pure + assert  
3. Phase 5 `register_league_season` + league cog wire  
4. **STOP** — demo Abandoned cannot newly join; double-join AlreadySeated  

### Incremental delivery

1. MVP join gate  
2. US4/US5 polish  
3. Apply/smoke/changelog/Lock  

### Suggested stop points

| Stop | When |
|------|------|
| Pure MVP | After T009 |
| Enforcement MVP | After T018 |
| Full child | After T033 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Same-file migration tasks (T011, T014–T015) = one authoring pass preferred
- Do not implement US-42.4–42.10 here
- Do not add new hubs or hard-delete tooling
- Commit only when user requests

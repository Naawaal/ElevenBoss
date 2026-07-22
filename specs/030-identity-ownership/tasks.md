# Tasks: Identity & Ownership (US-42.1)

**Input**: Design documents from `/specs/030-identity-ownership/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Parent**: `specs/029-game-integrity` (US-42)

**Tests**: Required by plan/quickstart/SC-001–004 — `tests/test_register_idempotency.py`, `tests/test_identity_lifecycle.py`, `tests/test_pending_rewards_current_owner.py` (+ guild non-delete grep/smoke).

**Locked decisions** (research.md):
- Migration `074_identity_ownership.sql` (after 073); harden `register_new_player` so `unique_violation` → `ALREADY_REGISTERED`
- Soft columns `identity_status` / `last_qualifying_activity_at` / `identity_status_changed_at`; thresholds 30/90 in `packages/player_engine/identity.py`
- Guild remove = pause only (verify; no delete)
- `claim_pending_level_rewards` already filters `owner_id` — add regression test
- No new slash commands; no multi-club; no XP/economy pipe rewrite
- Touch activity thinly via economy wrapper (or `identity_rpc`); heavy abandonment automation → US-42.3

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`…`[US5]` maps to spec user stories

---

## Phase 1: Setup — W0 audit

**Purpose**: Confirm current gaps before writing migration/code

- [x] T001 Run Validation 1 greps from `specs/030-identity-ownership/quickstart.md`; record findings in `specs/030-identity-ownership/checklists/requirements.md` Notes (register already-registered path, guild pause-only, claim owner filter)
- [x] T002 [P] Diff latest `register_new_player` in `supabase/migrations/055_recovery_energy_cap_cleanup.sql` (or newer replace if any) against `specs/030-identity-ownership/contracts/register-idempotency.md`; note missing `unique_violation` handler
- [x] T003 [P] Confirm next migration number is `074` (no `074_*.sql` yet) and list touch files from `specs/030-identity-ownership/plan.md` Structure section

**Checkpoint**: Gaps documented; ready to author 074

---

## Phase 2: Foundational — Migration 074 core (BLOCKS stories) 🎯

**Purpose**: Schema + concurrent-safe register + RPC stubs for lifecycle/ownership tooling

**⚠️ CRITICAL**: User stories depend on this migration existing (apply can wait until story verify, but SQL must be complete)

- [x] T004 Create `supabase/migrations/074_identity_ownership.sql`: `ALTER TABLE public.players` add `identity_status TEXT NOT NULL DEFAULT 'active'` with CHECK (`active`,`inactive`,`abandoned`), `last_qualifying_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `identity_status_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`; backfill existing rows; leave AI clubs as `active`
- [x] T005 In same migration: `CREATE OR REPLACE FUNCTION public.register_new_player(...)` per `contracts/register-idempotency.md` — keep EXISTS → `ALREADY_REGISTERED`; wrap insert so `unique_violation` also raises `ALREADY_REGISTERED`; set new identity columns on insert (`active`, NOW()); preserve starter card/squad behavior from current 055 body (diff carefully — do not drop age/potential/role fields)
- [x] T006 [P] In same migration: add `touch_club_activity(p_club_id BIGINT)`, `classify_club_identity_status(p_club_id BIGINT)`, `recover_club_identity(p_club_id BIGINT)` per `contracts/soft-lifecycle.md` (humans only for classify; no deletes; grants to anon/authenticated/service_role)
- [x] T007 Extend schema guards in `074` DO block and/or `supabase/scripts/verify_required_schema.sql` for new columns + functions (`touch_club_activity`, `classify_club_identity_status`, `recover_club_identity`, keep `register_new_player`)
- [x] T008 [P] Add `scratch/apply_migration_074.py` mirroring `scratch/apply_migration_073.py`
- [x] T009 [P] Add `scratch/smoke_identity_ownership_074.py` — assert columns exist; calling register twice on same id yields already-registered class error; classify no-op delete check

**Checkpoint**: Migration file complete; apply/smoke scripts ready

---

## Phase 3: User Story 1 — Register exactly one durable club (Priority: P1) 🎯 MVP

**Goal**: Double/concurrent register never creates a second club; abort leaves zero durable state

**Independent Test**: SC-001 — 100 scripted/double paths → ≤1 club per discord id; loser gets already-registered

### Tests

- [x] T010 [P] [US1] Create `tests/test_register_idempotency.py`: pure/SQL-or-mocked cases for ALREADY_REGISTERED path; document concurrent unique_violation → same exception family; assert whitespace name rejection still specified

### Implementation

- [x] T011 [US1] Apply `074` via `scratch/apply_migration_074.py` on target DB (when `DATABASE_URL` available); confirm second `register_new_player` raises `ALREADY_REGISTERED`
- [x] T012 [US1] Verify `apps/discord_bot/cogs/onboarding_cog.py` maps `ALREADY_REGISTERED` (and any unique-violation wrapped text) to friendly already-registered copy; adjust substring check only if needed
- [x] T013 [P] [US1] Confirm `/register` pre-check in `onboarding_cog.py` still short-circuits when `players` row exists (no second thread)

**Checkpoint**: US1 MVP — one club invariant enforceable under race

---

## Phase 4: User Story 2 — Own cards and coins under one identity (Priority: P1)

**Goal**: Current `owner_id` is authoritative; pending claims follow current owner; coins remain club-scoped via economy pipe (no pipe rewrite)

**Independent Test**: SC-003 — claim after ownership change credits new owner; card guards use `owner_id`

### Tests

- [x] T014 [P] [US2] Create `tests/test_pending_rewards_current_owner.py`: assert claim contract filters `player_cards.owner_id = p_owner_id` (SQL source grep or documented RPC behavior test); fail if stale `club_id`-only credit path reappears in migration text

### Implementation

- [x] T015 [US2] Audit `claim_pending_level_rewards` in latest migration defining it; if already correct per `contracts/ownership-current-owner.md`, leave RPC unchanged and note “verify-only” in checklist Notes — only patch via forward SQL in 074+ if audit fails
- [x] T016 [P] [US2] Grep `apps/discord_bot` for card mutations that trust client owner without RPC recheck; fix only clear bypasses (shared helper prefer) — no new hubs

**Checkpoint**: INV-02 / INV-14 regression-locked

---

## Phase 5: User Story 3 — Survive guild leave, bot remove, and re-add (Priority: P1)

**Goal**: Guild events never delete clubs/cards; re-add reuses same club

**Independent Test**: SC-002 — leave/remove simulations delete 0 clubs; pause seasons only

### Tests

- [x] T017 [P] [US3] Add grep-based test or checklist script section in `tests/test_guild_events_non_delete.py` (or extend an existing test module): `on_guild_remove` / `pause_seasons_for_guild` source must not call players delete

### Implementation

- [x] T018 [US3] Review `apps/discord_bot/main.py` `on_guild_remove` and `apps/discord_bot/core/guild_resolver.py` `pause_seasons_for_guild` against `contracts/guild-events-non-delete.md`; add a one-line comment citing US-42.1 non-delete if missing; change code only if a delete path exists
- [x] T019 [P] [US3] Confirm no per-guild club create on join; `/register` remains global identity (spot-check onboarding + guard)

**Checkpoint**: Cross-server durability frozen in code + test

---

## Phase 6: User Story 4 — Soft inactivity without destroying the club (Priority: P2)

**Goal**: Inactive/Abandoned labels without hard delete; recover same club; second register still blocked

**Independent Test**: Classify 30/90 thresholds; recover → active; register still ALREADY_REGISTERED

### Tests

- [x] T020 [P] [US4] Create `tests/test_identity_lifecycle.py`: pure tests for `packages/player_engine/player_engine/identity.py` thresholds (29d→active, 30d→inactive, 90d→abandoned) and status transition helpers

### Implementation

- [x] T021 [US4] Implement `packages/player_engine/player_engine/identity.py` with `INACTIVE_DAYS=30`, `ABANDONED_DAYS=90`, `classify_status(last_activity, now) -> str` (and any small pure helpers); export from `packages/player_engine/player_engine/__init__.py`
- [x] T022 [US4] Add `apps/discord_bot/core/identity_rpc.py` with async wrappers for `touch_club_activity`, `classify_club_identity_status`, `recover_club_identity` (supabase rpc calls only)
- [x] T023 [US4] Wire thin activity touch: after successful `apply_club_economy` in `apps/discord_bot/core/economy_rpc.py` (or documented single call site), invoke `touch_club_activity` best-effort (log failures; never roll back economy) — ponytail: one pipe, not every cog
- [x] T024 [P] [US4] Ensure `register_new_player` path cannot succeed for abandoned/inactive (same discord_id still EXISTS) — covered by PK; document in soft-lifecycle contract note if needed

**Checkpoint**: Soft labels exist; inventory never deleted by classify

---

## Phase 7: User Story 5 — Unregistered users cannot mutate; owner-bound interactions (Priority: P2)

**Goal**: Gated commands prompt `/register`; foreign onboarding / views reject non-owners

**Independent Test**: SC-004 — unregistered gated calls → 0 durable writes + register guidance

### Implementation

- [x] T025 [US5] Verify `apps/discord_bot/middleware/guard.py` `ensure_registered` still blocks with register copy; list major cogs using it (spot-check) — add missing `ensure_registered` only where a gated mutation clearly lacks it (minimal)
- [x] T026 [P] [US5] Verify onboarding views in `apps/discord_bot/cogs/onboarding_cog.py` reject `interaction.user.id != owner_id`; fix if any button skips the check
- [x] T027 [P] [US5] Stale confirm after success: ensure commit path hits RPC already-registered (covered by US1); optional disable view after success if easy one-liner in onboarding without new features

**Checkpoint**: Unregistered / non-owner paths fail closed

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Docs, verify schema, handoff

- [x] T028 Apply/verify: run `scratch/smoke_identity_ownership_074.py` and `supabase/scripts/verify_required_schema.sql` (or project verify script) when DB available; note skip if no `DATABASE_URL`
- [x] T029 [P] Run `pytest tests/test_register_idempotency.py tests/test_identity_lifecycle.py tests/test_pending_rewards_current_owner.py tests/test_guild_events_non_delete.py -q` (skip missing module only if T017 chose checklist-only — then run the files that exist)
- [x] T030 [P] Update `change_log.md` only if manager-visible identity behavior changed (soft status display or register copy); otherwise note “no player-facing change” in checklist
- [x] T031 [P] Optional: one-line pointer under `.specify/specs/v1.0.0/spec.md` US-01 or US-42 stub to `specs/030-identity-ownership/spec.md`
- [x] T032 Run full `specs/030-identity-ownership/quickstart.md` Validations 0–4 as applicable; mark `specs/030-identity-ownership/spec.md` Status → Locked when stories done
- [x] T033 Confirm zero new slash commands / no `packages/integrity` / no economy or XP pipe edits beyond touch side-effect; grep cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: Immediate
- **Phase 2 Foundational**: After Setup — **BLOCKS** US1–US4 DB-dependent work
- **Phase 3 US1**: After T005+ (register harden); MVP stop after T013
- **Phase 4 US2**: After Setup; can audit claim in parallel with Phase 2; tests parallel
- **Phase 5 US3**: Independent of 074 columns; can run parallel with Phase 2–3 after Setup
- **Phase 6 US4**: After T004–T006 (columns/RPCs) + T021 pure module
- **Phase 7 US5**: After Setup; parallel with US3
- **Phase 8 Polish**: After desired stories (min US1+US3 for durability MVP; full = all)

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 register harden | MVP |
| US2 | Claim audit; optional 074 | Mostly verify + test |
| US3 | Code review guild paths | Parallel early |
| US4 | Phase 2 lifecycle RPCs + identity.py | After columns |
| US5 | Guard/onboarding | Parallel |

### Parallel Opportunities

- T002 || T003 after T001
- T006 || T008 || T009 after T004/T005 started (T006 same file as T004 — sequential in one migration authoring session; T008/T009 parallel once SQL exists)
- T010 || T014 || T017 || T020 tests in parallel once contracts stable
- T018 || T025 after Setup
- T030 || T031 in Polish

### Parallel Example: After migration SQL exists

```text
Task: T008 scratch/apply_migration_074.py
Task: T009 scratch/smoke_identity_ownership_074.py
Task: T010 tests/test_register_idempotency.py
Task: T020 tests/test_identity_lifecycle.py (needs identity.py — after T021 or stub)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1–2 (074 register harden + columns/RPCs)  
2. Phase 3 US1 (apply + onboarding map + test)  
3. **STOP** — demo concurrent/double register safe  

### Incremental delivery

1. MVP US1 → race-safe register  
2. US3 → prove non-delete on guild events  
3. US2 → claim current-owner regression  
4. US4 → soft labels + touch  
5. US5 → guard/owner polish  
6. Polish → verify + changelog/SDD  

### Suggested stop points

| Stop | When |
|------|------|
| MVP | After T013 |
| Durability | After T019 |
| Full child | After T033 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Same-file migration tasks (T004–T007) should be one authoring pass even if listed separately
- Do not implement US-42.2–42.10 here
- Do not add hard-delete or multi-club
- Commit only when user requests

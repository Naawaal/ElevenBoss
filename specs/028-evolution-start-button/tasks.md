# Tasks: Evolution Start Button Fix

**Input**: Design documents from `/specs/028-evolution-start-button/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by plan/quickstart — `tests/test_evolution_gate.py` (keep/extend) + `tests/test_evolution_hub_copy.py` (cost constants / formula string).

**Locked decisions** (research.md):
- Grey Start button is intentional when slots full or real cooldown active; false lockout after live 6h is the bug
- `get_evolution_hub_status` must read same `game_config` keys as `start_player_evolution` (not hardcoded 10h / 10×OVR)
- Hub Resources cost copy → `500+5×OVR` (FR-006)
- Migration `073_evolution_hub_status_config.sql`; do not edit 023 in place on remote
- No new slash commands / tables; agent-context script skip

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]` / `[US2]` / `[US3]` maps to spec user stories

---

## Phase 1: Setup

**Purpose**: Confirm touch list before writing code

- [x] T001 Grep `get_evolution_hub_status`, `evolution_cooldown_hours`, `10×OVR`, `can_start`, `start_player_evolution` across `supabase/migrations/`, `apps/discord_bot/cogs/development_cog.py`, `packages/player_engine/`; confirm touch list matches `plan.md`

---

## Phase 2: Foundational — Hub status config alignment (BLOCKS all stories) 🎯 MVP core

**Purpose**: Server hub readiness uses live cooldown/cost config identical to start

**⚠️ CRITICAL**: User stories depend on this migration being written (apply can wait until verify phase, but bot copy can ship after T005)

- [x] T002 Create `supabase/migrations/073_evolution_hub_status_config.sql`: `CREATE OR REPLACE FUNCTION public.get_evolution_hub_status(p_owner_id BIGINT)` per `contracts/get-evolution-hub-status.md` — load `evolution_max_active`, `evolution_cooldown_hours` (default 10 fallback like start), `evolution_start_energy`, `evolution_start_flat`, `evolution_start_ovr_mult` via `get_game_config_int`; keep `can_cold_start` / `can_replace` / `can_start` semantics; return `start_coin_flat`, `start_coin_ovr_mult`, and set `start_coin_multiplier` to ovr mult (not legacy 10)
- [x] T003 In same migration body for T002: prefer `sync_action_energy` + read `action_energy` (and keep returning a field the cog already reads, e.g. dual-write `training_energy` or map into existing key) so Resources energy stays correct — do not break `55/120`-style display
- [x] T004 [P] Add `scratch/apply_migration_073.py` following latest scratch apply pattern (e.g. `scratch/apply_migration_072.py`)
- [x] T005 Confirm `supabase/scripts/verify_required_schema.sql` still guards `get_evolution_hub_status(bigint)` (extend only if new required objects appear — none expected)

**Checkpoint**: Migration file ready; eligibility math sourced from `game_config`

---

## Phase 3: User Story 1 — Click Start when eligible (Priority: P1) 🎯 MVP

**Goal**: After live cooldown with a free slot, **Start New Evolution** is enabled and opens track selection

**Independent Test**: Club with `0/3` and cooldown elapsed under config hours → hub Start clickable → track/player picker

### Tests

- [x] T006 [P] [US1] Create `tests/test_evolution_hub_copy.py`: assert `EVOLUTION_START_ENERGY`, `EVOLUTION_START_FLAT`, `EVOLUTION_START_OVR_MULT`, `EVOLUTION_START_COOLDOWN_HOURS` match documented live mirrors (25 / 500 / 5 / 6)

### Implementation

- [x] T007 [US1] Verify `ClubEvolutionsHubView` in `apps/discord_bot/cogs/development_cog.py` still enables Start solely from `can_start` + slot check (no extra hardcoded 10h); no change unless a stale local gate exists
- [x] T008 [US1] Apply `073` via `scratch/apply_migration_073.py` on target DB; SQL-check `get_evolution_hub_status(<test_owner>)` — for ~37m since start, `cooldown_remaining_seconds` ≈ 5h23m window (6h config), not ~9h23m

**Checkpoint**: Eligible clubs no longer falsely greyed after real cooldown; US1 MVP demoable after bot refresh

---

## Phase 4: User Story 2 — Understand why Start is blocked (Priority: P1)

**Goal**: When Start is disabled, Slots / Cooldown embed copy still explains the real block (full slots or remaining time on the **live** clock)

**Independent Test**: Full slots → disabled + slots copy; mid-cooldown no replacement → disabled + remaining time that matches 6h config

- [x] T009 [US2] Review `show_club_evolutions_hub` Cooldown / Slots / over-slot fields in `apps/discord_bot/cogs/development_cog.py`: ensure copy still uses `can_cold_start` / `can_replace` / `format_cooldown_remaining(cooldown_remaining_seconds)` and does not claim “Ready” while Start is disabled
- [x] T010 [P] [US2] Extend `tests/test_evolution_gate.py` if needed: cooldown seconds still produce remaining-time gate message; full/overflow slots still blocked — keep coverage for FR-004

**Checkpoint**: Blocked hubs remain understandable; timer honesty matches US1

---

## Phase 5: User Story 3 — Hub readiness matches start enforcement (Priority: P1)

**Goal**: Hub `can_start` / remaining seconds and `start_player_evolution` accept/reject agree on the same duration source

**Independent Test**: Scripted/SQL cases — inside cooldown both block; past cooldown both allow (slot permitting)

- [x] T011 [US3] Diff `get_evolution_hub_status` cooldown/cost keys in `073` against latest `start_player_evolution` in `supabase/migrations/062_p2p_transfer_market.sql` (or later replace) — same `get_game_config_int` keys and defaults
- [x] T012 [US3] Manual/SQL pair check per `quickstart.md`: after apply, hub JSON cost fields are 500/5 not multiplier 10; cooldown remaining agrees with start rejection timing within ~1 minute

**Checkpoint**: SC-002 / SC-004 — no multi-hour false lockout window

---

## Phase 6: Cost copy honesty (FR-006, same hub screen)

**Goal**: Resources line matches live start formula

**Independent Test**: Open Evolution Command Center → no `10×OVR`; shows flat+mult formula

- [x] T013 [US1] Update Resources cost string in `show_club_evolutions_hub` (`apps/discord_bot/cogs/development_cog.py`) per `contracts/evolution-hub-start-cost-copy.md` — prefer status `start_energy_cost` / `start_coin_flat` / `start_coin_ovr_mult` when present, else package constants; remove hardcoded `10×OVR`
- [x] T014 [P] [US1] Extend `tests/test_evolution_hub_copy.py` with a tiny helper or asserted format fragment for the hub cost line (flat+mult, not `10×OVR`)

**Checkpoint**: Same screen no longer lies about coins

---

## Phase 7: Polish & Cross-Cutting

- [x] T015 [P] Brief reconcile note in `.specify/specs/v1.0.0/spec.md` / `plan.md` — evolution hub status cooldown/cost aligned with `game_config` / start RPC
- [x] T016 Update `change_log.md` — player-facing: evolution Start cooldown display fixed (6h config); start cost copy `500+5×OVR`
- [x] T017 Run `pytest tests/test_evolution_gate.py tests/test_evolution_hub_copy.py -q`; run schema verify; walk `specs/028-evolution-start-button/quickstart.md` Discord checks; confirm no new slash commands

---

## Dependencies & Execution Order

### Phase Dependencies

```text
T001
 → T002 → T003 → T005          (migration body; T004∥ after T002 exists)
 → T004 [P]
 → T006 [P] → T007 → T008      (US1)
 → T009 → T010 [P]             (US2; after remaining seconds honest)
 → T011 → T012                 (US3 parity verify)
 → T013 → T014 [P]             (cost copy; can start after T002 fields known)
 → T015–T017                   (polish)
```

- **Foundational (T002–T005)** blocks truthful US1–US3 behavior on DB.
- **T013 cost copy** can ship in the same bot deploy as T007 without waiting on SQL if constants are used, but prefer status fields after T008.
- **Ship order**: write+apply `073` (T002–T008) → bot cost/gate (T007, T013) → changelog (T016).

### User Story Dependencies

| Story | Depends on | Independently testable when |
|-------|------------|-----------------------------|
| US1 Click when eligible | T002–T008 | Free slot + elapsed live cooldown → Start works |
| US2 Understand blocks | T002 + T009–T010 | Full slots / mid-cooldown hubs explain disable |
| US3 Hub = start rules | T002 + T011–T012 | SQL/hub/start agree on hours |

### Parallel Opportunities

- After T002 drafted: `T004` (scratch apply) ∥ `T005` (verify guard check) ∥ `T006` (package constant tests)
- After T008: `T010` ∥ `T011` (gate tests vs SQL key diff)
- Polish: `T015` ∥ early draft of `T016` once behavior confirmed

### Parallel Example: After migration drafted

```text
Task: scratch/apply_migration_073.py
Task: confirm verify_required_schema still lists get_evolution_hub_status
Task: tests/test_evolution_hub_copy.py constant mirrors
```

---

## Implementation Strategy

### MVP First (US1)

1. T001 → T002–T005 (migration)
2. T006–T008 (apply + Start enables when eligible)
3. **STOP and VALIDATE** with reporter club: remaining time on 6h clock; after expiry Start clickable
4. Then T009–T014 (block copy + cost honesty) and polish

### Incremental Delivery

1. Migration alone already fixes false grey-out for anyone past 6h still under old 10h display
2. Bot cost string removes `10×OVR` confusion on same screen
3. Changelog + SDD reconcile last

### Out of scope (do not task)

- Changing product cooldown length
- New evolution tracks / slash commands
- Making Discord disabled buttons clickable
- Fixing stale ephemeral after view timeout
- Redesigning cancel → replacement rules

---

## Notes

- Bisup: apply `073` on Supabase, then restart bot for Python cost-copy changes
- Reporter symptom (`9h 23m` with `0/3`) should become ~`5h Xx` immediately after apply if last start was ~37m ago
- All tasks use checklist format with IDs and file paths for `/speckit.implement`
- **2026-07-22 implement**: Applied 073; smoke owner `976054…` remaining+ago = 21600s (6h). Live `evolution_max_active` = **4**; Start button now trusts RPC `can_start` only (no package-3 clamp). Restart bot for embed cost copy.

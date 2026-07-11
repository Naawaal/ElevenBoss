# Tasks: Retirement Lifecycle Fixes

**Input**: Design documents from `/specs/007-retirement-lifecycle-fixes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require `tests/test_age_manager.py` (decline bands) and `tests/test_regen_pool.py` (rarity weights). Discord/RPC paths validated via `quickstart.md` (no Discord integration harness required).

**Organization**: Tasks grouped by user story (US1–US3) for incremental delivery.

**Locked decisions** (from research.md R1–R6):
- Decline: PAC/PHY ≥31 (−2 at ≥35); PAS/DEF/DRI ≥33; SHO ≥35; floor 1
- Auto-promote: `formation_slot_role` match; pick highest `overall` then lowest `id`
- `players.squad_invalid`; clear on full XI save or successful promote to 11
- Battle: count≠11 hard stop + retirement copy when flag true (bot/league/friendly)
- Regen rarity: ≥85 50/50 Epic/Rare; 80–84 60/40 Rare/Common; 75–79 80/20 Common/Rare
- Migration `053+`; no new tables/slash commands

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3
- Include exact file paths in descriptions

## Path Conventions

- Pure engine: `packages/player_engine/player_engine/`
- Bot: `apps/discord_bot/`
- SQL: `supabase/migrations/`, `supabase/scripts/verify_required_schema.sql`
- Tests: `tests/` at repo root
- Scratch: `scratch/`
- SDD: `.specify/specs/v1.0.0/`
- Feature docs: `specs/007-retirement-lifecycle-fixes/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm contracts and call sites before code

- [x] T001 Review `specs/007-retirement-lifecycle-fixes/plan.md` against `contracts/aging-decline-curve.md`, `contracts/retire-squad-vacancy-rpc.md`, `contracts/battle-squad-invalid-gate.md`, and `contracts/regen-rarity-weights.md`; note any drift in `specs/007-retirement-lifecycle-fixes/research.md` if found
- [x] T002 [P] Grep `supabase/migrations/041_player_age_lifecycle.sql`, `packages/player_engine/player_engine/age_manager.py`, `packages/player_engine/player_engine/regen_pool.py`, and `apps/discord_bot/cogs/battle_cog.py` for `process_season_aging`, `retire_player_card`, `yearly_stat_decline`, `xi_count` / `count != 11`, and `set_formation_and_assignments`; list exact edit points

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + RPC replacements that US1/US2 depend on; do not ship Discord gate until migration applied and verify passes

**⚠️ CRITICAL**: Apply `053` and pass `verify_required_schema.sql` before relying on `squad_invalid` or new decline SQL in production

- [x] T003 Create `supabase/migrations/053_retirement_lifecycle_fixes.sql`: add `players.squad_invalid BOOLEAN NOT NULL DEFAULT FALSE`; replace `process_season_aging` per `contracts/aging-decline-curve.md` (include `sho`/`dri` in SELECT/UPDATE; DRI@33+, SHO@35+); replace `retire_player_card` per `contracts/retire-squad-vacancy-rpc.md` (capture slot → delete → retire → auto-promote via `formation_slot_role` or set `squad_invalid`; clear flag if XI returns to 11); replace `set_formation_and_assignments` to clear `squad_invalid` when 11 assignments written; end with schema guard for column + functions
- [x] T004 [P] Add `scratch/apply_migration_053.py` (follow existing scratch apply pattern) and extend `supabase/scripts/verify_required_schema.sql` for `column:public.players.squad_invalid` (and ensure `retire_player_card` / `process_season_aging` / `set_formation_and_assignments` remain in function guards)
- [x] T005 Apply migration via `scratch/apply_migration_053.py` (or equivalent) against the target DB and run `supabase/scripts/verify_required_schema.sql` until green

**Checkpoint**: Column exists; RPCs replaced; verify passes; no Discord copy changes yet

---

## Phase 3: User Story 1 — Veterans Lose All-Around Edge (Priority: P1) 🎯 MVP

**Goal**: Late-career decline touches DRI (33+) and SHO (35+) so veterans are not immortal finishers/dribblers

**Independent Test**: `yearly_stat_decline(33)` includes `dri: -1` (and pas/def); `yearly_stat_decline(35)` includes `sho: -1` and `dri: -1`; SQL aging for a birthday into 33/35 drops those attrs (quickstart §1)

### Tests for User Story 1

- [x] T006 [P] [US1] Extend `tests/test_age_manager.py` to assert decline bands for ages 31, 33, and 35 per `contracts/aging-decline-curve.md` (including PAS/DEF alignment at 33–34 and floors)

### Implementation for User Story 1

- [x] T007 [US1] Update `yearly_stat_decline` in `packages/player_engine/player_engine/age_manager.py` to match the contract table (DRI@33+, SHO@35+; PAS/DEF@33+; PAC/PHY −2 at ≥35); keep age &lt; 31 returning empty/no-op
- [x] T008 [US1] Confirm `supabase/migrations/053_retirement_lifecycle_fixes.sql` `process_season_aging` loop matches T007 (same deltas, floors, `recalculate_card_ovr`); fix any Python/SQL drift found
- [x] T009 [US1] Run `pytest tests/test_age_manager.py -q` and fix until green

**Checkpoint**: Pure + SQL decline curves aligned; immortal SHO/DRI exploit closed in formula space

---

## Phase 4: User Story 2 — Retirement Does Not Leave a Silent Squad Hole (Priority: P1)

**Goal**: Retiring a starter auto-promotes a same-role reserve or flags `squad_invalid` and blocks match starts with `/squad` guidance

**Independent Test**: Retire starter with matching reserve → slot filled, flag false; retire without cover → flag true + battle blocked; save full XI → flag clear + battle allowed (quickstart §2–§4)

### Implementation for User Story 2

- [x] T010 [US2] Verify `retire_player_card` in `supabase/migrations/053_retirement_lifecycle_fixes.sql` returns JSON with `vacated_slot`, `promoted_card_id`, `squad_invalid` and uses highest-`overall` then lowest-`id` for promote; smoke-call RPC on a test club if DB available
- [x] T011 [US2] Add a shared XI gate helper (or inline consistently) in `apps/discord_bot/cogs/battle_cog.py` per `contracts/battle-squad-invalid-gate.md`: if `squad_invalid` or assignment count ≠ 11, block with retirement copy when flag true, else existing incomplete-XI copy; apply to bot, league, and friendly start paths
- [x] T012 [US2] Ensure friendly start in `apps/discord_bot/cogs/battle_cog.py` validates **both** challenger and opponent XI / `squad_invalid` before acquiring locks or spawning the match
- [x] T013 [P] [US2] Optional: when `squad_invalid` is true, show a short warning on the `/squad` hub embed in `apps/discord_bot/cogs/squad_cog.py` / `apps/discord_bot/embeds/squad_embeds.py` (fetch `players.squad_invalid` in `fetch_squad_data`)
- [x] T014 [US2] Grep `apps/discord_bot/` for other match-start entry points that load `squad_assignments` without an 11-player / invalid check; align or document intentional skips (e.g. bot-vs-bot auto-sim already failing on empty XI)
- [x] T014b [US2] Verify league auto-sim and bot match paths in `apps/discord_bot/` (and any `match_engine` callers) safely skip or fail closed when `squad_invalid = TRUE` or starting XI count &lt; 11; document the exact call site that handles each guard in `specs/007-retirement-lifecycle-fixes/research.md` or a short note under this task when done

**Checkpoint**: No human match starts with a retirement hole; repair path is `/squad` only

---

## Phase 5: User Story 3 — Legend Regens Feel Like Legends (Priority: P2)

**Goal**: Regen rarity scales with retired peak OVR; ≥85 never Common

**Independent Test**: Seeded n≥200 samples per band within ±5 pp of FR-014 weights; ≥85 Common count = 0 (quickstart §5)

### Tests for User Story 3

- [x] T015 [P] [US3] Extend `tests/test_regen_pool.py` with seeded distribution tests for OVR 88, 82, and 77 calling `regen_rarity_for_ovr` / `generate_regen_from_retired` per `contracts/regen-rarity-weights.md`

### Implementation for User Story 3

- [x] T016 [US3] Implement `regen_rarity_for_ovr` in `packages/player_engine/player_engine/regen_pool.py` with exact FR-014 weights; replace inverted nested-probability chain in `generate_regen_from_retired`
- [x] T017 [P] [US3] Export `regen_rarity_for_ovr` from `packages/player_engine/player_engine/__init__.py` if tests/callers need it
- [x] T018 [US3] Confirm `apps/discord_bot/tasks/regen_pool_job.py` still works with updated generator (no eligibility/threshold changes); run `pytest tests/test_regen_pool.py -q`

**Checkpoint**: Legend regens are Rare/Epic-only; mid bands match weights

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene across all three stories

- [x] T019 [P] Update player-facing notes in `change_log.md` for the three retirement fixes (decline, squad hole, regen rarity)
- [x] T020 [P] Reconcile `.specify/specs/v1.0.0/spec.md` AC-31d (decline attrs) and AC-34 regen rarity notes, and matching bullets in `.specify/specs/v1.0.0/plan.md`
- [x] T021 Run `specs/007-retirement-lifecycle-fixes/quickstart.md` automated section (`pytest tests/test_age_manager.py tests/test_regen_pool.py -q`) and tick manual checklist items that can be done locally
- [x] T022 Grep to confirm no new slash commands/tables; no `discord` imports under `packages/`; no leftover inverted rarity logic; superseded decline comments updated

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** production ship of US1 SQL / US2 flag
- **US1 (Phase 3)**: Needs T003 decline SQL (or implement Python first, then align in T008); tests T006 can start after T001
- **US2 (Phase 4)**: Depends on Foundational (column + retire RPC); Discord gate after T005
- **US3 (Phase 5)**: Independent of US1/US2 after Setup — can parallel with Foundational Discord work
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3 — MVP balance fix
- **US2 (P1)**: Needs migration foundational; independent of US3
- **US3 (P2)**: Pure package + tests only; parallelizable with US1/US2

### Within Each Story

- Tests (where listed) before or with implementation; fail-first preferred for new asserts
- Confirm SQL/Python parity before marking US1 done
- Battle paths updated together for US2 (bot + league + friendly)

### Parallel Opportunities

```text
After T001:
  T002 (grep) || start drafting T003 outline

After T003 started:
  T004 (scratch + verify) in parallel with finishing T003 body

After Setup:
  T015+T016+T017+T018 (US3) || T006+T007 (US1 Python) while T005 applies migration

After T005:
  T010 || T011 (then T012) || T013 optional
```

---

## Parallel Example: After Foundational

```bash
# US1 math + US3 rarity in parallel (different files):
Task: "Update yearly_stat_decline in packages/player_engine/player_engine/age_manager.py"
Task: "Implement regen_rarity_for_ovr in packages/player_engine/player_engine/regen_pool.py"
Task: "Extend tests/test_age_manager.py"
Task: "Extend tests/test_regen_pool.py"

# Then US2 Discord gate (single cog — sequential within story):
Task: "XI gate helper + bot/league paths in apps/discord_bot/cogs/battle_cog.py"
Task: "Friendly dual-club validation in apps/discord_bot/cogs/battle_cog.py"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup
2. Phase 2 Foundational (at least decline half of `053` + verify)
3. Phase 3 US1 Python + tests
4. **STOP and VALIDATE** decline curve
5. Ship balance fix even if squad/regen follow

### Incremental Delivery

1. Setup + Foundational → schema/RPCs ready
2. US1 → immortal-shooter closed
3. US2 → no silent squad holes
4. US3 → legend regen fantasy
5. Polish → changelog + SDD + quickstart

### Suggested MVP scope

**US1 (decline curve)** is the smallest high-value ship. Prefer shipping **US1 + US2** together if Monday aging is imminent (squad holes hurt more in live ops than rarity).

---

## Notes

- [P] = different files, no incomplete-task dependency
- Do not edit applied `041_*.sql` in place on remote — forward `053` only
- Auto-promote ignores injury/fatigue by design (research R2)
- Commit after each phase or logical group when asked
- Stop at any checkpoint to validate the story independently

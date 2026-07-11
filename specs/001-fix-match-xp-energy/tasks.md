# Tasks: Fix Match XP + Energy Regen

**Input**: Design documents from `/specs/001-fix-match-xp-energy/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require unit coverage for regen minutes-to-full and XP payload/recovery hydration (AGENTS.md non-trivial logic check).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Bot: `apps/discord_bot/`
- Migrations / verify: `supabase/migrations/`, `supabase/scripts/`
- Tests: `tests/` at repo root
- SDD: `.specify/specs/v1.0.0/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm feature docs and remote schema baseline before code changes

- [x] T001 Review `specs/001-fix-match-xp-energy/spec.md`, `plan.md`, `contracts/match-xp-rpc.md`, and `contracts/energy-regen-display.md` against locked decisions (bot/league XP; regen 0.25)
- [x] T002 Confirm remote DB state: `apply_card_xp` is SECURITY DEFINER and `game_config.energy_regen_per_min` = `0.25` (apply `supabase/migrations/048_apply_card_xp_security_definer.sql` and/or `supabase/migrations/046_progression_energy_rebalance.sql` via existing scratch apply scripts if missing)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema verify hardening so missing DEFINER cannot silently pass — blocks reliable US1 shipping

**⚠️ CRITICAL**: Complete before treating US1 as done in production

- [x] T003 Extend `supabase/scripts/verify_required_schema.sql` to fail when `public.apply_card_xp(uuid,integer,text)` exists but `prosecdef` is false
- [x] T004 [P] Add forward migration `supabase/migrations/049_verify_apply_card_xp_security_definer.sql` with an idempotent DO guard asserting `apply_card_xp` SECURITY DEFINER (do not edit 048 in place)

**Checkpoint**: Verify script / 049 guard catches missing DEFINER; 046/048 applied on target DB

---

## Phase 3: User Story 1 — Match XP After Bot or League Match (Priority: P1) 🎯 MVP

**Goal**: Bot and league matches grant development XP to eligible starting cards; hard XP failures surface to the manager; league recovery does not KeyError on missing `name`

**Independent Test**: Complete a bot match (and a league match) with cards under the daily match-XP cap; card XP/level increases. Force XP RPC failure in staging → manager sees error and `xp_applied_at` stays null.

### Tests for User Story 1

- [x] T005 [P] [US1] Add unit test that `build_process_match_result_rpc` succeeds with hydrated card dicts (`id`, `name`) in `tests/test_match_loop_hardening.py`
- [x] T006 [P] [US1] Add unit test that id-only recovery-style cards raise/fail clearly OR that a hydration helper returns name-complete cards before XP build in `tests/test_match_loop_hardening.py`

### Implementation for User Story 1

- [x] T007 [US1] In `apps/discord_bot/cogs/battle_cog.py` league recovery path (`recovery=True`), hydrate starting cards from `player_cards` (at least `id`, `name`, and fields used by `effective_card_age`) instead of `{"id": cid}` only before `apply_league_human_rewards`
- [x] T008 [US1] Verify bot path in `apps/discord_bot/core/match_rewards.py` still calls `apply_match_xp_if_needed` with `match_type="bot"` and does not mark `xp_applied_at` on failure (`apps/discord_bot/core/match_xp.py`)
- [x] T009 [US1] Verify league path in `apps/discord_bot/core/league_rewards.py` still calls `apply_match_xp_if_needed` with `match_type="league"` under the same idempotency rules
- [x] T010 [US1] Ensure hard XP failures in bot/league flows surface a manager-visible error embed in `apps/discord_bot/cogs/battle_cog.py` (FR-004) — do not swallow `process_match_result` exceptions after coins apply without messaging
- [x] T011 [US1] Grep `apps/discord_bot/` for callers of `apply_match_xp_if_needed` / `process_match_result` and confirm bot + league only (no accidental friendly wiring)

**Checkpoint**: US1 independently testable — bot/league XP works; recovery hydrated; hard fail visible

---

## Phase 4: User Story 2 — Faster Passive Energy Regen (Priority: P2)

**Goal**: Empty→full ≈ 6h 40m at max 100; hub/status and insufficient-energy copy match 1-per-4-minutes (not 6 min / ~10h)

**Independent Test**: `minutes_to_full_action_energy(0, 100)` ≈ 400; status string and error copy reference 4-minute regen

### Tests for User Story 2

- [x] T012 [P] [US2] Add/extend unit test in `tests/test_economy_flows.py` or `tests/test_match_loop_hardening.py` asserting `minutes_to_full_action_energy(0, 100) == 400` (and not 600) using updated regen default

### Implementation for User Story 2

- [x] T013 [US2] Update `REGEN_PER_MIN` default to `1/4` (0.25) in `apps/discord_bot/core/economy_rpc.py` and wire `minutes_to_full_action_energy` / `format_action_energy_status` to that default
- [x] T014 [US2] Prefer reading `get_game_config_numeric(db, 'energy_regen_per_min', 0.25)` on async display paths in `apps/discord_bot/core/economy_rpc.py` where a DB handle is already available (keep sync helpers with 0.25 fallback)
- [x] T015 [P] [US2] Update insufficient-energy copy in `apps/discord_bot/core/api_errors.py` from “every 6 minutes” to “every 4 minutes” (or config-derived equivalent)
- [x] T016 [P] [US2] Update player-facing regen wording in `change_log.md` to 1 energy per 4 minutes / ~6h 40m full
- [x] T017 [US2] Grep `apps/discord_bot/` and `change_log.md` for stale “6 minutes” / “10h” energy regen strings and fix remaining player-facing hits

**Checkpoint**: US2 independently testable — display and DB rate agree at ~6h 40m full

---

## Phase 5: User Story 3 — Friendlies Stay Sandbox (Priority: P3)

**Goal**: Confirm friendlies still spend no energy and grant no XP after US1/US2 changes

**Independent Test**: Friendly completion path still has no `apply_match_xp_if_needed` / economy XP; footer still states no XP/coins

### Implementation for User Story 3

- [x] T018 [US3] Confirm `apps/discord_bot/cogs/battle_cog.py` friendly completion does not call `apply_match_xp_if_needed` or spend action energy; keep “No energy spent. No coins or XP earned.” footer
- [x] T019 [P] [US3] Add or extend a regression assertion in `tests/test_match_loop_hardening.py` (or adjacent test) documenting that friendly match_type is not used by bot/league reward helpers for XP grants

**Checkpoint**: Friendly sandbox unchanged

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: SDD reconcile, verify, cleanup

- [x] T020 [P] Reconcile regen rate (1/6 → 1/4) and match-XP restore notes in `.specify/specs/v1.0.0/spec.md`
- [x] T021 [P] Reconcile matching energy/XP notes in `.specify/specs/v1.0.0/plan.md`
- [x] T022 Run `pytest tests/test_match_loop_hardening.py tests/test_economy_flows.py -q` and fix failures
- [x] T023 Run schema verify (`python scratch/verify_schema_full.py` or `psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql`) per `specs/001-fix-match-xp-energy/quickstart.md`
- [x] T024 Walk quickstart.md scenarios (bot XP, energy display, friendly sandbox) and note any gaps
- [x] T025 Remove any temporary debug instrumentation added during this fix in touched cogs/helpers (do not leave new agent logs)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: After Setup — blocks production confidence for US1
- **US1 (Phase 3)**: After Foundational (T003–T004); MVP
- **US2 (Phase 4)**: After Setup; can proceed in parallel with US1 after T002 (regen config confirmed)
- **US3 (Phase 5)**: After US1 implementation (T007–T011) so regression check is meaningful
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 schema guards + remote 048; no dependency on US2
- **US2 (P2)**: Depends on remote 046 / regen config; independent of US1 code paths
- **US3 (P3)**: Verification after US1; must not regress friendly sandbox

### Parallel Opportunities

- T003 and T004 can be drafted together; T004 after T003 pattern is clear
- T005 || T006 (tests)
- T015 || T016 (copy files)
- T020 || T021 (SDD files)
- US1 and US2 can be implemented in parallel by different people after Phase 1–2

---

## Parallel Example: User Story 1

```bash
# Tests in parallel:
Task: "T005 unit test hydrated build_process_match_result_rpc in tests/test_match_loop_hardening.py"
Task: "T006 unit test recovery hydration / id-only failure in tests/test_match_loop_hardening.py"

# Then sequential implementation:
Task: "T007 hydrate league recovery cards in apps/discord_bot/cogs/battle_cog.py"
Task: "T008–T011 verify call sites + FR-004 messaging + grep"
```

## Parallel Example: User Story 2

```bash
Task: "T012 minutes-to-full == 400 test"
Task: "T015 api_errors.py 4-minute copy"
Task: "T016 change_log.md regen wording"
# After T013 constant update:
Task: "T014 optional async config read for display"
Task: "T017 grep stale 6-minute strings"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup (T001–T002)
2. Phase 2 Foundational (T003–T004) + apply 048 if needed
3. Phase 3 US1 (T005–T011)
4. **STOP and VALIDATE**: Bot/league XP on staging
5. Ship MVP if energy can wait

### Incremental Delivery

1. Setup + Foundational → schema safe
2. US1 → match XP restored (MVP)
3. US2 → regen + UI (~6h 40m)
4. US3 → friendly regression confirmed
5. Polish → SDD + quickstart + pytest

### Suggested MVP Scope

**T001–T011 only** (schema DEFINER + bot/league XP + recovery hydration + FR-004). US2/US3 follow in the same PR if capacity allows (small diff).

---

## Notes

- Do not grant friendly XP; do not change store refill costs/caps
- Do not bypass `apply_card_xp` / `process_match_result`
- Daily 100 XP/card/day cap remains (FR-009)
- Commit only when the user asks
- All tasks use checklist format: `- [ ] Txxx ...` with file paths

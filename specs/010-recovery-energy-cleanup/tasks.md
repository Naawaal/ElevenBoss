# Tasks: Recovery Energy, Hub Cleanup & Energy Cap

**Input**: Design documents from `/specs/010-recovery-energy-cleanup/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Update energy default tests if they assert max=100 as a default; fatigue math unchanged.

**Locked decisions** (research.md):
- Recovery energy → 5 via `game_config` DO UPDATE + RPC fallback
- Energy max → 120; **must** relax `energy`/`training_energy` CHECK ≤100
- Store facilities: strip Hospital chrome; keep `HospitalPanelView` for Profile
- Delete `/club-finances` slash only; keep finance helpers
- Migration `055_recovery_energy_cap_cleanup.sql`

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Grep `fatigue_recovery_energy`, `energy_max`, `max_energy`, ``/100``, `club-finances`, `Hospital Panel`, `build one in the Store` across `apps/`, `packages/`, `supabase/`, `change_log.md`; note touch list against plan.md

---

## Phase 2: Foundational (Migration 055)

- [x] T002 Create `supabase/migrations/055_recovery_energy_cap_cleanup.sql` per `contracts/migration-055.md` (CHECK relax, config upserts, max_energy backfill, RPC fallbacks, register defaults)
- [x] T003 [P] Add `scratch/apply_migration_055.py`; apply migration; run `verify_required_schema.sql`
- [x] T004 [P] Update Python defaults: `packages/energy/energy/models.py`, `apps/discord_bot/core/economy_rpc.py` (maximum default 120)

**Checkpoint**: Config shows recovery=5, energy_max=120; energy can exceed 100 without CHECK failure

---

## Phase 3: US1 — Recovery energy 5

- [x] T005 [US1] Ensure Development Recovery preview/fallback uses 5 in `apps/discord_bot/cogs/development_cog.py` (`get_game_config_int(..., 5)` not Basic-drill default)
- [x] T006 [US1] Confirm `process_recovery_session` reads config 5 (migration T002)

---

## Phase 4: US2 — Energy cap 120 UI

- [x] T007 [US2] Replace hardcoded ``/100`` action-energy displays in `apps/discord_bot/cogs/development_cog.py` with dynamic max from sync
- [x] T008 [P] [US2] Update `.get("max_energy", 100)` → `120` in `store_cog.py`, `profile_cog.py`, `development_cog.py`
- [x] T009 [US2] Adjust `tests/test_match_loop_hardening.py` if defaults encode max=100 incorrectly

---

## Phase 5: US3 — Store facilities without Hospital

- [x] T010 [US3] Strip Hospital field/buttons/copy from facilities hub in `apps/discord_bot/views/store_facilities.py`; keep `HospitalPanelView` / `show_hospital_panel`
- [x] T011 [P] [US3] Update Hospital pointers in `profile_embeds.py`, `api_errors.py`, `development_cog.py`, `injury_rpc.py` per `contracts/copy-cleanup.md`

---

## Phase 6: US4 — Remove `/club-finances`

- [x] T012 [US4] Remove `club-finances` slash command from `apps/discord_bot/cogs/economy_cog.py`; keep Profile Finances helpers
- [x] T013 [P] [US4] Grep and fix README/`change_log.md` player pointers to `/club-finances` and Store Hospital

---

## Phase 7: Polish

- [x] T014 [P] Reconcile `.specify/specs/v1.0.0/spec.md` + `plan.md`; brief `AGENTS.md` note if energy max documented
- [x] T015 Update `change_log.md` with Recovery 5⚡, energy max 120, Hospital Profile-only, `/club-finances` removed
- [x] T016 Run pytest subset + quickstart grep validation; mark complete

---

## Dependencies

Setup → Foundational → US1/US2/US3/US4 (US3/US4 parallel after Foundational) → Polish

## MVP

T002–T008 + T010–T012 (config + UI + command removal)

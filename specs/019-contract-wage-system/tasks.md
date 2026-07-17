# Tasks: Contract & Wage System

**Input**: Design documents from `/specs/019-contract-wage-system/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pure-math unit tests from plan (`tests/test_wage_payroll_math.py`) — required by AGENTS for non-trivial wage/grace/strike formulas. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Wage scope = **Starting XI only**; derive wages (no per-card wage column)
- Flag `wages_payroll_enabled` default **false**; `wages_payroll_bill_scale` for soft launch
- Unpaid = partial pay → debt + strikes; **no auto-sell**; AI (`is_ai`) exempt
- Strikes: ≥2 block friendlies; ≥3 block new P2P list + scout; league/bot OK; agent sale OK
- Contract: renew days config default 7; grace 7 days → **match XI block**; no auto-release v1
- Migration: `063_contract_wage_system.sql`; scheduler Monday **00:05 UTC**
- Extend `/profile` Finances + existing renew — **no new slash command**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema work

- [x] T001 Grep `calculate_weekly_wages`, `renew_contract`, `apply_club_economy`, `squad_validity`, `economy_cog`, `season_aging_job`, `create_transfer_listing`, `purchase_scouting_player` callers; confirm touch list matches `specs/019-contract-wage-system/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_063.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure math, schema, RPCs — **MUST complete before Finances/payroll UX and strike gates**

**⚠️ CRITICAL**: No Finances payroll copy, match/strike gates, or scheduler wiring until this phase is done and schema verify passes

- [x] T003 [P] Implement `packages/economy/economy/wages.py` per `contracts/wage-formula.md` and `contracts/contract-expiry-gates.md`: `card_weekly_wage`, XI bill helper, `strike_blocks_friendly`, `strike_blocks_market`, `contract_in_grace`, `contract_blocks_xi`
- [x] T004 [P] Refactor `packages/economy/economy/engine.py` `calculate_weekly_wages` to call `card_weekly_wage` (preserve existing OVR base behavior when multipliers = 1.0)
- [x] T005 [P] Export wage/contract helpers from `packages/economy/economy/__init__.py`; mirror config defaults in `packages/economy/economy/config.py` and/or `packages/economy/economy/flows.py`
- [x] T006 [P] Add `tests/test_wage_payroll_math.py` covering OVR base wage, bill_scale, rarity mult, grace/block windows, strike thresholds, debt/strike reset rules (pure; no Discord)
- [x] T007 Author `supabase/migrations/063_contract_wage_system.sql`: alter `players` add `payroll_debt`, `payroll_strikes`, `last_payroll_at`, `last_payroll_week`; create `payroll_runs` + unique `(club_id, week_key)` + indexes + RLS per `data-model.md`; seed `game_config` keys; helper `wages_payroll_enabled()`; null `contract_expires_at` backfill `NOW() + 30 days`; schema guard block. **Include T037 strike peer-guards** on transfer/scout RPCs in this same migration file.
- [x] T008 In `063_contract_wage_system.sql`, implement wage SQL helpers (per-card + XI bill) matching package formula per `contracts/wage-formula.md`
- [x] T009 In `063_contract_wage_system.sql`, add `process_club_weekly_payroll(p_club_id, p_week_key)` per `contracts/process-weekly-payroll.md` (`FOR UPDATE`, debt-first apply, strikes, `apply_club_economy` source `weekly_payroll`, idempotent `payroll_runs`)
- [x] T010 In `063_contract_wage_system.sql`, add batch `process_weekly_payroll(p_week_key DEFAULT NULL)` that skips when flag off / `is_ai`, processes human clubs missing a run for the week
- [x] T011 Extend `supabase/scripts/verify_required_schema.sql` with columns/table/RPCs/policies/config from 063 (correct `split_part` for functions/policies)
- [x] T012 Apply migration via `scratch/apply_migration_063.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green

**Checkpoint**: Schema verified; `pytest tests/test_wage_payroll_math.py -q` green; bot wiring can begin

---

## Phase 3: User Story 1 — See and understand the wage bill (Priority: P1) 🎯 MVP

**Goal**: Finances shows XI wage bill + (when flag on) debt/strikes/next payroll; flag off keeps “not auto-deducted”

**Independent Test**: `/profile` → Finances → bill matches Starting XI formula; flag off copy unchanged; flag on shows debt/strikes/next Monday hint

### Implementation for User Story 1

- [x] T013 [US1] Update `apps/discord_bot/cogs/economy_cog.py` `fetch_club_finances_embed` to compute bill via package helpers (XI from `squad_assignments`); show paying-player count
- [x] T014 [US1] Flag-aware Finances copy in `apps/discord_bot/cogs/economy_cog.py` per `contracts/finances-ui.md`: flag off → keep *(not auto-deducted)*; flag on → debt, strikes, last/next payroll, remove “not auto-deducted”
- [x] T015 [P] [US1] Add bot helper to read `wages_payroll_enabled` (e.g. `apps/discord_bot/core/economy_rpc.py` or small helper beside existing config reads)

**Checkpoint**: US1 independently demoable — Finances truth without requiring a live payroll run

---

## Phase 4: User Story 2 — Weekly payroll runs automatically (Priority: P1)

**Goal**: Monday job (and smoke RPC) deducts wages via economy pipe when flag on; idempotent per week

**Independent Test**: Flag on → `process_club_weekly_payroll` debits bill; re-run same week no double debit; flag off → no coin change

### Implementation for User Story 2

- [x] T016 [P] [US2] Add `apps/discord_bot/tasks/weekly_payroll_job.py` calling `process_weekly_payroll` and logging processed/skipped counts
- [x] T017 [US2] Wire Monday **00:05 UTC** job in `apps/discord_bot/core/scheduler_jobs.py` and `apps/discord_bot/main.py` (after aging at 00:00)
- [x] T018 [US2] Ensure Finances SELECT in `apps/discord_bot/cogs/economy_cog.py` includes `payroll_debt`, `payroll_strikes`, `last_payroll_at`, and the latest `payroll_runs` row fields for UI display
- [x] T019 [P] [US2] Add `scratch/smoke_weekly_payroll.py` for flag off skip + paid run; assert second same-week call → zero second debit (covers T036 / SC-001)

**Checkpoint**: Scheduler + RPC path proven; ledger source `weekly_payroll` only

---

## Phase 5: User Story 3 — Can’t pay — fair consequences (Priority: P1)

**Goal**: Partial pay creates debt/strikes; ladder blocks friendlies then market actions; recovery path clear in UI

**Independent Test**: Force low coins → partial payroll → strikes≥1 visible; ≥2 blocks friendly; ≥3 blocks P2P list/scout; agent sale OK; clean pay clears strikes

### Implementation for User Story 3

- [x] T020 [US3] Gate friendly match start when `strike_blocks_friendly` in `apps/discord_bot/cogs/battle_cog.py` (or shared pre-match check) with ephemeral explaining wages/Finances recovery
- [x] T021 [P] [US3] Bot UX pre-check for new P2P listings when `strike_blocks_market` in `apps/discord_bot/views/marketplace_transfer.py` (friendly ephemeral before RPC; server still enforces via T037)
- [x] T022 [P] [US3] Gate both regen `purchase_scouting_player` (`apps/discord_bot/cogs/marketplace_cog.py`) and academy `dispatch_youth_scout` / `sign_youth_scout_prospect` (`apps/discord_bot/views/academy_hub.py`) against payroll strikes at the UI layer; leave **agent sale** unrestricted; server enforces via T037
- [x] T023 [US3] Finances strike ladder hint copy in `apps/discord_bot/cogs/economy_cog.py` (what ≥2 / ≥3 mean); confirm league/bot paths remain open
- [x] T037 [US3] Implement RPC-side rejection in `create_transfer_listing`, `purchase_scouting_player`, `dispatch_youth_scout`, and `sign_youth_scout_prospect` when `payroll_strikes >= payroll_strike_market_block` (in `063_contract_wage_system.sql` or follow-up alter in same migration). Prevents client-side bypass (Constitution Principle II). Agent sale stays allowed.

**Checkpoint**: Unpaid ladder demoable without losing the club; agent cash faucet still works; RPC guards block bypass

---

## Phase 6: User Story 4 — Contracts that matter (Priority: P2)

**Goal**: Grace warnings; past-grace XI blocks match via `squad_validity`; renew still works; age ≥35 renew blocked

**Independent Test**: XI card past grace → match blocked with renew/replace message; renew extends; in-grace still playable with warning

### Implementation for User Story 4

- [x] T024 [US4] Extend `apps/discord_bot/core/squad_validity.py` per `contracts/contract-expiry-gates.md`: load XI `contract_expires_at`; past grace → invalid with named card message; grace → warn flag for UI. Reject **squad assign** of past-grace cards into `squad_assignments` (FR-007 / US4).
- [x] T025 [US4] Confirm match entry uses updated `squad_validity`: grep league lock/start + bot match paths for `squad_validity` / `human_club_xi_ok`; list affected files (`battle_cog.py` and peers) and wire any silent bypass. Verify past-grace XI blocks league matches.
- [x] T026 [US4] Profile renew in `apps/discord_bot/cogs/player_cog.py`: pass `p_extension_days` from `contract_renewal_days` config (default 7); show grace/expired warning on profile embed. **Checklist:** verify renew age ≥35 still raises exception (FR-008).
- [x] T027 [P] [US4] Finances contract alerts (count XI in grace / past grace) in `apps/discord_bot/cogs/economy_cog.py`

**Checkpoint**: Expiry has teeth at match lock; renew remains the recovery path

---

## Phase 7: User Story 5 — Migration / safe enablement (Priority: P2)

**Goal**: Existing clubs safe; flag-off regression; soft `bill_scale`; AI exempt

**Independent Test**: Flag off Finances + job no debit; AI skipped; scale 0.5 halves bill; backfill left no null expiries

### Implementation for User Story 5

- [x] T028 [US5] Verify migration backfill left no null `contract_expires_at` (SQL check in smoke or `scratch/smoke_weekly_payroll.py`)
- [x] T029 [US5] Document ops soft-launch steps in `specs/019-contract-wage-system/quickstart.md` (flag + optional `wages_payroll_bill_scale = 0.5`); ensure defaults remain false / 1.0 in migration seed
- [x] T030 [US5] AI exempt assertion in smoke: `is_ai` club → `skipped_ai`, coins unchanged

**Checkpoint**: Rollout-safe; SC-005 flag-off holds

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, changelog, integrity

- [x] T031 [P] Update `change_log.md` with weekly payroll + debt/strikes + contract grace/match gate + flag rollout note
- [x] T032 [P] Reconcile economy / contract ACs in `.specify/specs/v1.0.0/spec.md` (and plan notes if needed) for wages/contracts
- [x] T033 Grep for direct `players.coins` updates, leftover “not auto-deducted” when flag on, and any wage math duplicated outside `packages/economy/economy/wages.py` / `engine.py`; fix leftovers
- [x] T034 Run `specs/019-contract-wage-system/quickstart.md` validation (pytest + schema + flag off/on smoke + expiry gate)
- [x] T035 Run integrity pass: every new RPC has a call site (scheduler + smoke); renew still via `apply_club_economy`; no `discord` imports under `packages/`; no auto-sell / morale-mutation code shipped; confirm `senior_roster_cap` unchanged (FR-010)
- [x] T036 Covered by T019 smoke idempotency assert (keep as checklist): second `process_club_weekly_payroll` same week → zero second debit (SC-001)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup** → no deps
- **Phase 2 Foundational** → after Setup; **BLOCKS** all story wiring that assumes schema
- **Phase 3 US1** → after Foundational (Finances MVP; works flag off/on)
- **Phase 4 US2** → after Foundational (payroll RPC); Finances T014 benefits from runs existing
- **Phase 5 US3** → after payroll can create strikes (US2) OR seed `payroll_strikes` for UI-only tests; **T037 in migration 063** before production flag
- **Phase 6 US4** → after Foundational (grace helpers); parallel with US1 Finances alerts
- **Phase 7 US5** → after US2 smoke path
- **Phase 8 Polish** → after desired stories complete

### User Story Dependencies

```text
Foundational (math + 063 RPCs incl. T037 strike guards)
    ├── US1 Finances bill/copy
    ├── US2 Payroll job + smoke ── US3 Strike gates (UI + RPC)
    ├── US4 Contract grace / XI assign + match block
    └── US5 Soft enable / AI / backfill checks
Polish (changelog + quickstart + integrity)
```

### Parallel Opportunities

- T001 || T002
- T003 || T005 || T006 (T004 after T003)
- After T012: T013–T015 (US1) || T016–T019 (US2) || T024–T027 (US4)
- T021 || T022 after strike helpers exist (T037 ships with 063)
- T031 || T032

### Parallel Example: After Foundation

```text
T013–T015  economy_cog Finances + flag helper
T016–T017  payroll job + main.py cron
T024–T025  squad_validity + battle/league paths
```

---

## Implementation Strategy

### MVP First (US1 + foundation)

1. Phase 1 + Phase 2 (migration + math + verify + T037 RPC strike guards)
2. Phase 3 US1 (Finances truth) — demoable with flag **off**
3. **STOP** — validate Independent Test for US1
4. Then US2 payroll before any production flag flip

### Incremental Delivery

1. Foundation → schema green (+ RPC strike guards)  
2. US1 → Finances truth  
3. US2 → Monday payroll + smoke  
4. US3 → strike ladder UI + confirm T037  
5. US4 → contract grace / assign + match teeth  
6. US5 → soft launch / AI / backfill  
7. Polish → changelog + SDD + full quickstart  

### Suggested MVP scope

**T001–T015** (Setup + Foundational + US1). Do not enable production flag until **US2 (T016–T019)**, **US3 (T020–T023 + T037)**, and smoke idempotency pass in staging.

---

## Notes

- [P] = different files, no incomplete deps
- All coin paths: `apply_club_economy` only — never direct `players.coins`
- Wage scope stays XI-only until a future spec; do not silently bill reserves
- Cancel/renew when flag off: renew unchanged; payroll no-ops
- Prefer helpers in `packages/economy/economy/wages.py` over cog-local formulas
- Analyze remediations (2026-07-14): I1 no auto-release; I2 no morale; I3 XI-only; U1 T037 RPC strike guards; U2 both scout paths; U3 T018 concrete; U4 age≥35 + league grep; A1/S1 SC-003 + Status
- Commit after each logical group when asked; do not push/flag prod without verify
- Do **not** mix Evolutions 018 work into this task list

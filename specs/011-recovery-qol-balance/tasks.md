# Tasks: Recovery QoL Balance

**Input**: Design documents from `/specs/011-recovery-qol-balance/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Update `tests/test_fatigue_injury_math.py` for new drain / passive / bench / recovery-day asserts (required for formula change).

**Locked decisions** (research.md):
- Injury bases **1 / 4 / 7** via SQL CASE + Python `BASE_RECOVERY_DAYS` (no new `game_config` injury keys)
- Passive base **25** + TG×5; bench **+25**; base drain **18**
- Mid-injury **forward-only** (no ETA backfill)
- Migration `056_recovery_qol_balance.sql`
- Drain must ship with bot (`FATIGUE_BASE_DRAIN`); config alone is ops mirror

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Grep `WHEN 1 THEN 3`, `BASE_RECOVERY_DAYS`, `FATIGUE_PASSIVE_BASE`, `FATIGUE_BASE_DRAIN`, `FATIGUE_BENCH_PER_MATCH`, `fatigue_passive_base`, `fatigue_bench_per_match`, `fatigue_base_drain`, `AC-39h`, and changelog TG/bench lines; confirm touch list matches `plan.md`

---

## Phase 2: Foundational (Migration 056)

**Purpose**: Live DB config + injury CASE; blocks correct prod injury ETAs and passive/bench until applied

- [x] T002 Create `supabase/migrations/056_recovery_qol_balance.sql` per `contracts/game-config-fatigue-retune.md` + `contracts/injury-base-days.md`: upsert `fatigue_passive_base=25`, `fatigue_bench_per_match=25`, `fatigue_base_drain=18` (`ON CONFLICT DO UPDATE`); `CREATE OR REPLACE` `process_post_match_injuries` and `admit_to_hospital` with `CASE … 1/4/7`; end-of-migration config guards; **no** UPDATE of open `hospital_patients`
- [x] T003 [P] Add `scratch/apply_migration_056.py` (clone `055` pattern); apply migration; run `python scratch/verify_schema_full.py` or `verify_required_schema.sql`; confirm config SELECT shows 25/25/18

**Checkpoint**: New admits use 1/4/7; daily recovery + bench read new config; open injuries unchanged

---

## Phase 3: US1 — Injury bases 1/4/7 (P1) 🎯 MVP

**Goal**: Minor/Moderate/Major untreated clocks are Discord-friendly; Hospital still shortens

**Independent Test**: `recovery_days_for_tier` unit asserts; optional staging admit

- [x] T004 [P] [US1] Update `BASE_RECOVERY_DAYS = {1: 1, 2: 4, 3: 7}` in `packages/player_engine/player_engine/injury_math.py`
- [x] T005 [US1] Update hospital recovery asserts in `tests/test_fatigue_injury_math.py` (`recovery_days_for_tier(1,0)==1`, `(2,3)==3`, `(3,0)==7`)

**Checkpoint**: Pure math + SQL CASE agree; FR-001/FR-002 covered

---

## Phase 4: US2 — Passive base 25 (P1)

**Goal**: Non-hospital daily passive = `25 + TG×5` (TG3=+40)

**Independent Test**: `passive_recovery_amount(1/3/5) == 30/40/50`

- [x] T006 [P] [US2] Set `FATIGUE_PASSIVE_BASE = 25` (and deprecated `FATIGUE_PASSIVE_PER_DAY` alias) in `packages/player_engine/player_engine/fatigue.py`; refresh module comment defaults
- [x] T007 [US2] Update passive asserts in `tests/test_fatigue_injury_math.py` (TG1/5 and `apply_passive_recovery` cases)

**Checkpoint**: Config (T002) + Python preview math match FR-003 / SC-003

---

## Phase 5: US3 — Bench rest +25 (P2)

**Goal**: Competitive unused bench gains +25 fatigue

**Independent Test**: `apply_bench_rest` / `FATIGUE_BENCH_PER_MATCH == 25`

- [x] T008 [P] [US3] Set `FATIGUE_BENCH_PER_MATCH = 25` in `packages/player_engine/player_engine/fatigue.py`
- [x] T009 [US3] Update bench asserts in `tests/test_fatigue_injury_math.py`

**Checkpoint**: Live bench via config (T002); Python default matches FR-004

---

## Phase 6: US4 — Base drain 18 (P2)

**Goal**: Starter match drain base 18 (PHY/tactic/intensity still apply)

**Independent Test**: PHY70 / attack / intensity → **21**; bot deploy required for live drain

- [x] T010 [P] [US4] Set `FATIGUE_BASE_DRAIN = 18` and update docstring example in `packages/player_engine/player_engine/fatigue.py`
- [x] T011 [US4] Update `test_drain_gdd_example` in `tests/test_fatigue_injury_math.py` to expect **21**

**Checkpoint**: FR-005 / SC-005; drain ships with bot package deploy

---

## Phase 7: Polish

- [x] T012 [P] Reconcile `.specify/specs/v1.0.0/spec.md` **AC-39h** (and any injury-base mentions) for passive `25+TG×5`, bench +25, drain 18, injury 1/4/7; brief `plan.md` note if needed
- [x] T013 Update `change_log.md` player-facing Fatigue / Recovery lines (TG passive, bench, injury clocks, lighter drain)
- [x] T014 Grep confirms zero remaining `WHEN 1 THEN 3`, old `BASE_RECOVERY_DAYS` / `FATIGUE_*` defaults, stale AC-39h/changelog; run `pytest tests/test_fatigue_injury_math.py -q`; quickstart config SELECT if DB available

---

## Dependencies

```text
T001 → T002 → T003
         ↓
   ┌─────┼─────────┬──────────┐
   ↓     ↓         ↓          ↓
  US1   US2       US3        US4
 (T004–5)(T006–7)(T008–9) (T010–11)  ← Python/tests parallel after T002 authored
         ↓
      T012–T014 Polish
```

- **T002** is the only SQL blocking task for live injury/passive/bench.
- **US4 drain** is independent of migration for *code* but deploy bot + `056` together so config/docs stay aligned.
- US1–US4 file overlap: `fatigue.py` / `injury_math.py` / same test file — prefer sequential edits on those three files even if stories are logically parallel.

## Parallel opportunities

- After T002 is written: T004 ∥ T006 ∥ T008 ∥ T010 if different authors avoid colliding on the same files.
- T003 (apply) can run once T002 lands.
- T012 ∥ T013 after math/tests green.

## MVP (shippable increment)

T002–T005 + T006–T007 (injury + passive) → largest QoL win; then T008–T011 for rotation/drain coherence; then polish.

## Out of scope (do not task)

- Recovery Session energy/amount, Hospital UI/costs, injury chance, penalty tiers, mid-injury ETA rewrite, Store consumables, new slash commands

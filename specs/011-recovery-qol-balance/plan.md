# Implementation Plan: Recovery QoL Balance

**Branch**: `011-recovery-qol-balance` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-recovery-qol-balance/spec.md`

## Summary

Balance/QoL retune only: compress injury base days **3/8/20 → 1/4/7**, raise non-hospital passive base **15 → 25** (still `+ TG×5`), bench rest **15 → 25**, match base drain **22 → 18**. Hospital curve, Recovery Session, injury chance, and penalty tiers stay unchanged. Mid-injury stays **forward-only** (no ETA backfill).

**Technical approach**: Migration `056` upserts `game_config` fatigue keys and replaces `process_post_match_injuries` + `admit_to_hospital` CASE bases; mirror constants in `player_engine` (`fatigue.py`, `injury_math.py`); update unit tests + player-facing `change_log.md` + SDD AC-39h.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, supabase async client, `player_engine` (pure math)

**Storage**: Supabase Postgres — `game_config` upserts; `CREATE OR REPLACE` on injury admit paths only (no new tables/columns)

**Testing**: pytest — `tests/test_fatigue_injury_math.py` (drain example, passive/bench amounts, `recovery_days_for_tier`)

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — SQL config + pure formula defaults; no new Discord surface

**Performance Goals**: N/A (constant retune)

**Constraints**: AGENTS.md — no Discord in packages; mutations via existing RPCs; new numbered migration only; no new slash commands/hubs; forward-only injury dates; reconcile `.specify/specs/v1.0.0/`; update `change_log.md` on ship

**Scale/Scope**: ~8–12 files; 1 migration; no schema shape change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Constants in `packages/player_engine`; no Discord imports |
| II. DB via RPC/migration | PASS | Config + CASE via `056`; no cog loops / direct fatigue UPDATEs |
| III. Typing | PASS | Existing typed helpers; no new models required |
| IV. Slash + defer | PASS | No new commands; existing flows unchanged |
| V. APScheduler | PASS | Daily recovery job already calls TG-scaled RPC |
| VI. Friendly errors | PASS | No new error surfaces |
| VII. YAGNI | PASS | Numbers only; no Store consumables / Rest toggles |

**Post-Phase 1 re-check**: PASS — injury bases remain CASE+Python (not new config keys) per research R2; drain remains Python-authored with config mirror for ops docs.

## Project Structure

### Documentation (this feature)

```text
specs/011-recovery-qol-balance/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── game-config-fatigue-retune.md
│   ├── injury-base-days.md
│   └── pure-math-mirrors.md
└── tasks.md             # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/056_recovery_qol_balance.sql   # NEW
scratch/apply_migration_056.py                     # NEW

packages/player_engine/player_engine/fatigue.py     # drain 18, passive base 25, bench 25
packages/player_engine/player_engine/injury_math.py # BASE_RECOVERY_DAYS 1/4/7

tests/test_fatigue_injury_math.py                  # assert new numbers + drain example
change_log.md                                      # player-facing QoL note
.specify/specs/v1.0.0/spec.md                      # AC-39h + injury base mentions
.specify/specs/v1.0.0/plan.md                      # brief reconcile if present
```

**Structure Decision**: One forward migration for config + injury RPC CASE; Python mirrors for drain (bot computes drains) and UI/preview math; Discord cogs untouched except if any hardcoded copy is found at implement time (audit: none in apps today).

## Complexity Tracking

> No constitution violations. Empty by design.

## Implementation Notes (for `/speckit.tasks`)

1. **Order**: Apply `056` + verify config/guards before relying on new injury ETAs in prod.
2. **Drain path**: Bot builds drains in `injury_rpc.build_starter_drains` → `match_fatigue_drain` (Python). Updating `FATIGUE_BASE_DRAIN` is **required**; `game_config.fatigue_base_drain` is ops/docs mirror (not currently read by bot).
3. **Bench / passive path**: SQL already reads `game_config`; upsert alone changes live behavior. Still update Python defaults + `get_game_config_int` fallbacks when replacing daily recovery / match fatigue if touched.
4. **Injury path**: Hardcoded `CASE … 3/8/20` in `process_post_match_injuries` and `admit_to_hospital` (migration `050`) — must `CREATE OR REPLACE` both with `1/4/7`. Mirror `BASE_RECOVERY_DAYS` in Python.
5. **Mid-injury**: Do **not** UPDATE open `hospital_patients.expected_recovery_date` (forward-only).
6. **Out of scope**: Recovery Session energy/amount, Hospital costs/beds UI, injury chance, penalty tiers, friendlies fatigue, Store consumables.
7. **Grep after**: `WHEN 1 THEN 3`, `BASE_RECOVERY_DAYS`, `FATIGUE_PASSIVE_BASE`, `FATIGUE_BASE_DRAIN`, `fatigue_passive_base`, AC-39h, changelog TG passive line.

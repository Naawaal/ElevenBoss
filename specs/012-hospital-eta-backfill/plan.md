# Implementation Plan: Hospital ETA Backfill

**Branch**: `012-hospital-eta-backfill` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-hospital-eta-backfill/spec.md`

## Summary

One-time **fair recalculation** of open Hospital stays (and overflow untreated injuries) left on pre-011 long clocks. Credit time already served; never lengthen ETAs; early-discharge when past the new total; best-effort Medical Update DMs for early discharges only.

**Technical approach**: Migration `057` adds idempotent RPC `backfill_injury_eta_fairness()` that applies SQL updates atomically and returns a JSON summary; pure helpers in `injury_math.py` for the same formula + unit tests; `scratch/apply_migration_057.py` applies SQL; optional `scratch/notify_hospital_eta_backfill.py` (or bot one-shot) DMs from the RPC result — notifications never roll back data.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py (DM only), supabase/psycopg for apply, `player_engine.injury_math`

**Storage**: Supabase Postgres — no new tables/columns; UPDATE `hospital_patients` + `player_cards`; optional `CREATE OR REPLACE FUNCTION backfill_injury_eta_fairness()`

**Testing**: pytest — pure fair-recalc helpers (hospital ETA, overflow remaining, never-lengthen, early-clear)

**Target Platform**: Ops one-shot against hosted Supabase (+ optional Discord DMs)

**Project Type**: Monorepo — migration + pure math + scratch ops; no new slash commands

**Performance Goals**: Single-pass over open patients (expected small N); one transaction preferred

**Constraints**: AGENTS.md — no Discord in packages; atomic RPC preferred over cog loops; depend on **056 / 011** applied; never lengthen; idempotent; no new hubs; update `change_log.md` + SDD note

**Scale/Scope**: ~6–10 files; 1 migration; optional notifier script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Formula in packages; Discord DM only in apps/scratch |
| II. DB via RPC/migration | PASS | One RPC/batch; no per-row cog UPDATEs |
| III. Typing | PASS | Typed pure helpers |
| IV. Slash + defer | PASS | No new commands |
| V. APScheduler | PASS | Not a recurring job |
| VI. Friendly errors | PASS | DM best-effort; panel is source of truth |
| VII. YAGNI | PASS | One RPC + scratch apply; no Store heals |

**Post-Phase 1 re-check**: PASS — candidate ETA anchored to `admission_date + new_total` (research R1) for idempotency; early discharge mirrors `process_daily_recovery` clear path.

## Project Structure

### Documentation (this feature)

```text
specs/012-hospital-eta-backfill/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── backfill-injury-eta-rpc.md
│   ├── fair-recalc-math.md
│   └── early-discharge-notify.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
supabase/migrations/057_hospital_eta_backfill.sql   # NEW — RPC + optional invoke
scratch/apply_migration_057.py                      # NEW
scratch/notify_hospital_eta_backfill.py              # NEW optional — DMs from summary

packages/player_engine/player_engine/injury_math.py  # fair_eta / overflow remaining helpers
packages/player_engine/player_engine/__init__.py      # export if needed
tests/test_injury_eta_backfill.py                    # NEW pure tests

change_log.md
.specify/specs/v1.0.0/spec.md                        # AC note for mid-injury fairness pass
```

**Structure Decision**: Data mutation lives in one SECURITY DEFINER RPC (callable once from apply script). Pure Python mirrors formulas for tests. Discord notification is a separate best-effort step after commit.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **Prerequisite**: `056` applied (bases 1/4/7 live).
2. **Hospital ETA**: `candidate = admission_date + (new_total_days || ' days')::interval`; `final = LEAST(expected_recovery_date, candidate)`; if `NOW() >= final` → early recovery discharge.
3. **new_total_days**: same as admit — `CEIL(base / (1 + 0.2 * hospital_level))` with bases 1/4/7; `hospital_level` from current `players.hospital_level`.
4. **Early discharge end-state**: Match `process_daily_recovery` hospital clear — `discharge_date = NOW()`, clear `injury_tier` / `injury_started_at` / `injury_recovery_days` / `in_hospital`, grant `+25` fatigue (cap 100).
5. **Sync**: Update `player_cards.injury_recovery_days` to remaining whole days consistent with new ETA for in-hospital cards still injured.
6. **Overflow**: `injury_tier IS NOT NULL AND in_hospital = FALSE`; remaining = `min(old_days, max(0, ceil(new_base − elapsed_days)))`; clear if 0.
7. **DMs**: After RPC returns `early_discharged[]` with owner_id + names; never inside the SQL transaction.
8. **Out of scope**: Changing 011 formulas, mass heal, new commands, rewriting historical discharged rows.

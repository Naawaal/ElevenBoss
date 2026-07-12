# Implementation Plan: Daily Drill Cap Desync Fix

**Branch**: `013-daily-drill-reset` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-daily-drill-reset/spec.md`

## Summary

Fix Training Drills showing remaining club capacity while the action fails with the **club** limit message. Root causes in this codebase:

1. **Friendly-error substring bug** — per-card exception text contains `"Daily drill limit reached"`, so `api_error_message` maps it to the **club** (20) copy while the hub still shows e.g. `6/20`.
2. **Hub ignores soft-reset** — UI reads raw `daily_drill_count` without `daily_drill_reset_at` / UTC day rule used by RPCs.
3. **RPC soft-reset inconsistency** — `process_recovery_session` uses `v_reset IS NULL OR v_reset < CURRENT_DATE`; `process_stat_drill` (043) only uses `v_reset < CURRENT_DATE` (NULL never resets).
4. **Stuck rows** — optional repair reconciling `daily_drill_count` to today’s successful log usage when the column falsely sits at the cap.

**Not** adding `clubs.daily_drills_used` or making `process_daily_recovery` the sole drill reset owner.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+

**Primary Dependencies**: Existing Discord bot, Supabase RPCs, `player_engine` (new tiny pure helper)

**Storage**: `players.daily_drill_count`, `players.daily_drill_reset_at`, `player_drill_daily_log`; migration `058`

**Testing**: pytest — `api_error_message` ordering; pure `effective_daily_drill_count`; optional SQL self-check in scratch

**Target Platform**: Bisup bot + hosted Supabase

**Project Type**: Monorepo bugfix (UI + RPC + ops repair)

**Constraints**: AGENTS.md — no Discord in packages; atomic RPCs; no new slash commands; reconcile SDD; `change_log.md` brief note

**Scale/Scope**: ~8 files; 1 migration; ops repair script

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Pure day-count helper in packages; UI in apps |
| II. DB via RPC | PASS | Repair via RPC/SQL batch; no cog UPDATE loops |
| III. Typing | PASS | Typed helper |
| IV. Slash + defer | PASS | Existing hub; already deferring on training menu |
| V. APScheduler | PASS | Optional nightly persist only if cheap; not required for MVP |
| VI. Friendly errors | PASS | Fix mapping is core |
| VII. YAGNI | PASS | No clubs table; no new hubs |

**Post-Phase 1 re-check**: PASS — message-order fix is the highest-likelihood explanation of “6/20 + club limit copy”; soft-reset alignment still required for real stale counters.

## Project Structure

### Documentation (this feature)

```text
specs/013-daily-drill-reset/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-error-drill-limits.md
│   ├── effective-daily-drill-count.md
│   ├── process-stat-drill-soft-reset.md
│   └── repair-daily-drill-counts.md
└── tasks.md
```

### Source Code (repository root)

```text
supabase/migrations/058_daily_drill_cap_desync.sql   # NEW
scratch/apply_migration_058.py                       # NEW
scratch/repair_daily_drill_counts.py                 # NEW (ops; can call RPC)

packages/player_engine/player_engine/drill_caps.py   # NEW — effective_daily_drill_count
packages/player_engine/player_engine/__init__.py      # export

apps/discord_bot/core/api_errors.py                  # longest-key / ordered match
apps/discord_bot/cogs/development_cog.py             # select reset_at; display effective count

tests/test_api_errors.py                             # per-card vs club mapping
tests/test_drill_caps.py                             # NEW pure soft-reset display math

change_log.md
.specify/specs/v1.0.0/spec.md                        # brief AC note
supabase/scripts/verify_required_schema.sql          # if new RPC guarded
```

**Structure Decision**: Fix client error mapping first (smallest high-impact), align display + SQL soft-reset, then idempotent repair for stuck columns.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **api_errors**: Match **longest** friendly key substring first (or check per-card key before club key). Add regression test with message `Daily drill limit reached for this player (max 5 per day)`.
2. **Pure helper**: `effective_daily_drill_count(count, reset_at, today) -> int` — 0 if reset_at is None or reset_at < today else count (clamped ≥0).
3. **UI**: `select("daily_drill_count, daily_drill_reset_at, training_ground_level")`; display effective count.
4. **Migration 058**: `CREATE OR REPLACE process_stat_drill` with null-safe soft-reset matching recovery; optionally extract shared SQL snippet comments; `CREATE OR REPLACE` recovery only if needed for parity comments.
5. **Repair**: `repair_daily_drill_counts()` sets `daily_drill_count` to `LEAST(20, SUM(log.count) for owner's cards where drill_date = CURRENT_DATE)` and `daily_drill_reset_at = CURRENT_DATE` when column is inconsistent (e.g. count ≥ 20 but sum &lt; 20, or reset_at &lt; today → count 0). Idempotent.
6. **Out of scope**: Changing caps; clubs table; rewriting fatigue recovery formulas.

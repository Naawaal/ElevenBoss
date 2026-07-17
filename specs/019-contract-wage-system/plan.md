# Implementation Plan: Contract & Wage System

**Branch**: `019-contract-wage-system` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-contract-wage-system/spec.md`

## Summary

Turn forecast-only Starting XI wages into a **feature-flagged weekly payroll sink**, keep `renew_contract` as the renewal path, and give `contract_expires_at` **grace → XI block** teeth — without day-1 fire-sales or a new slash command.

**Technical approach**: Migration **`063_contract_wage_system.sql`** — `game_config` flag + tunables, club payroll debt/strikes columns, `payroll_runs` idempotency table, atomic RPC `process_weekly_payroll` (per club or batch) via `apply_club_economy`, helpers for wage math + contract playability, Monday UTC scheduler job. Pure wage/strike ladder helpers in `packages/economy`. Extend `/profile` Finances + squad/match validity + optional profile renew reminders. Flag default **false** (Finances stays “forecast only” until enablement).

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, existing `economy` + `apply_club_economy`

**Storage**: Supabase — alter `players` (debt/strikes), new `payroll_runs`, `game_config` keys; RLS if table exposed via Data API; extend `verify_required_schema.sql`

**Testing**: pytest for wage formula + strike ladder + grace windows; RPC smoke via scratch; Discord quickstart for Finances copy + flag off/on

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (packages + discord_bot + migrations)

**Performance Goals**: Weekly payroll set-based or batched club loops; single-club RPC under job timeout; Finances embed stays one-load

**Constraints**: AGENTS.md / constitution — no `discord` in `packages/`; coins only via `apply_club_economy`; new columns/RPCs only in **063**; defer interactions; no new slash; no auto-sell of stars in v1; YAGNI

**Scale/Scope**: 1 migration; economy helpers; Finances + squad_validity + scheduler; config flag default false; backfill null contracts only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Wage/ladder math in `packages/economy`; Discord only in `apps/discord_bot/` |
| II. DB via RPC | PASS | Payroll + debt mutations in RPCs; coins via `apply_club_economy` |
| III. Typing / Pydantic | PASS | Typed helpers + result models at package boundary |
| IV. Slash + defer | PASS | Extend `/profile` Finances + existing renew; no `/wages` |
| V. APScheduler | PASS | Monday UTC payroll job beside aging |
| VI. Friendly errors | PASS | Map RPC/insufficient/flag messages to embeds |
| VII. YAGNI | PASS | XI-only bill; no FM negotiations; no auto-fire-sale; optional release deferred |

**Post-Phase 1 re-check**: PASS — debt/strikes on `players`; derive wages (no per-card wage column); contract teeth via squad_validity; bot clubs exempt.

## Project Structure

### Documentation (this feature)

```text
specs/019-contract-wage-system/
├── plan.md
├── research.md              # assessment + frozen decisions
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── wage-formula.md
│   ├── process-weekly-payroll.md
│   ├── contract-expiry-gates.md
│   └── finances-ui.md
└── tasks.md                 # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
supabase/migrations/063_contract_wage_system.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_063.py

packages/economy/economy/engine.py              # extend / keep calculate_weekly_wages (+ multipliers)
packages/economy/economy/wages.py               # NEW — per-card wage, bill from XI, strike ladder helpers
packages/economy/economy/config.py / flows.py   # defaults mirroring game_config
packages/economy/economy/__init__.py            # exports

packages/player_engine/.../age_manager.py       # keep can_renew_contract; optional grace helpers
# or packages/economy/contracts.py for grace/playable windows (prefer economy/wages + player_engine age)

apps/discord_bot/cogs/economy_cog.py            # Finances: bill, debt, strikes, last/next payroll, flag-aware copy
apps/discord_bot/cogs/player_cog.py             # renew reminders / expiry warnings; extension days from config
apps/discord_bot/core/squad_validity.py         # past-grace contracts invalidate XI / block match
apps/discord_bot/core/scheduler_jobs.py         # process_weekly_payroll_job
apps/discord_bot/tasks/weekly_payroll_job.py    # optional thin task
apps/discord_bot/main.py                        # Monday 00:00 UTC job (after or with aging)
apps/discord_bot/cogs/battle_cog.py             # ensure match path uses squad_validity (already)

tests/test_wage_payroll_math.py                 # NEW

change_log.md                                   # on implement ship
.specify/specs/v1.0.0/spec.md                   # reconcile economy/contracts US on implement
```

**Structure Decision**: Extend existing economy + profile + scheduler layout; do not add apps/packages.

## Complexity Tracking

> No constitution violations requiring justification.

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research + decisions | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Frozen implementation decisions (from research)

| ID | Decision |
|----|----------|
| **D1** | **Wage scope v1 = Starting XI only** (`squad_assignments` → cards). Forecast ≡ payroll bill base. Bench/academy/reserves unpaid in v1. |
| **D2** | **Derive wages** at forecast/payroll time — **no** `player_cards.weekly_wage` column. |
| **D3** | Base formula unchanged: `(max(OVR,40)−40)² × wage_scale_factor + 10`. Optional rarity/age/POT multipliers via `game_config` (defaults: rarity Common=1.0 … Legendary=1.15; age/POT = 1.0 identity in v1 so bills ≈ today’s forecast until ops tunes). |
| **D4** | Flag `wages_payroll_enabled` default **false**. Soft bill scale `wages_payroll_bill_scale` default `1.0` (ops may set `0.5` for first live week). |
| **D5** | Unpaid v1: debit `min(coins, bill+debt_priority)`; **debt** accumulates remainder; **strikes** +1 if any unpaid wage/debt remains after run; full clear of debt+full wage pay → strikes = 0. **No auto-sell.** |
| **D6** | Strike ladder: **≥1** Finances warning; **≥2** block **friendly** matches; **≥3** block **new** P2P listings + youth scout spends (`purchase_scouting_player`, `dispatch_youth_scout`, `sign_youth_scout_prospect`) — enforced in **RPCs** (T037) plus bot UX. Agent sale still allowed. League/bot matches stay playable so debts can be paid. |
| **D7** | Contract renew: keep RPC + coin cost formula; **`contract_renewal_days`** config default **7** (matches UI today); age ≥35 block unchanged. |
| **D8** | Expiry teeth: **`contract_grace_days` = 7**. Within grace after expiry: playable + warning. **Past grace**: cannot be **assigned** to Starting XI (`squad_assignments`) and cannot match with past-grace XI — renew or replace. **No** auto-release in v1. |
| **D9** | **`is_ai` clubs exempt** from payroll (skip run, no strikes). |
| **D10** | Idempotency: `payroll_runs(club_id, week_key)` unique; ledger source `weekly_payroll`; key `weekly_payroll:{club_id}:{week_key}`. |
| **D11** | Scheduler: Monday **00:05 UTC** (after aging at 00:00) → `process_weekly_payroll` batch. |
| **D12** | Migration **063**; extend verify + RLS on `payroll_runs` if Data-API exposed; include T037 strike peer guards. |
| **D13** | Mid-week XI / transfer changes affect **next** Monday bill only (no retro mid-week payroll). |
| **D14** | Backfill: null `contract_expires_at` → `NOW() + 30 days` once; no coin wipe on migration. |
| **D15** | **No morale mutation** on unpaid wages (YAGNI). |

## Next command

`/speckit.implement` — migration 063, payroll RPCs, Discord wiring (T001+).

**Tasks**: [tasks.md](./tasks.md) (T001–T037)

**Analyze remediations**: 2026-07-14 — locked (no morale, XI-only, RPC strike guards, no auto-release).

**Note**: Evolutions overhaul is **018** — plan/implement separately; do not merge scopes.

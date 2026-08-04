# Implementation Plan: Youth Academy Rarity-Cap Redesign

**Branch**: `051-youth-academy-rarity` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/051-youth-academy-rarity/spec.md`

**US citation**: **US-42.2** (player state / academy holding) · **US-42.7** (economy — scout/promote fees via `apply_club_economy`) · **US-42.9** (DB invariants / rarity ceilings). Aligns academy generation with Feature **049** caps (US-23 progression single-pipe unchanged — academy growth stays auto-stat ticks, not `apply_card_xp`). Extends Feature **015**.

## Summary

Rebalance the existing Youth Academy so every academy-generated or academy-signed prospect obeys global rarity POT ceilings (Common 75 / Rare 85 / Epic 92 / Legendary 99), while cutting retention pressure (capacity **3/3/4/4/5**, intake **2**, weekly promote/sign ledger) and making potential discovery progressive (visible ranges + per-prospect scout narrowing — Deep no longer dumps exact POT by default).

**Technical approach**: Keep `player_cards.in_academy` as the holding model (no second inventory). Replace Common-only intake/gem bumps with rarity-weighted V2 generation validated against `rarity_potential_cap` / `assert_card_potential_integrity`. Add prospect scout-bound columns + assessment RPCs; rebalance discovery scouting under shared capacity + weekly signing counters. Cut over live academies (repair illegal POT, grandfather over-capacity, init ranges) behind `game_config` feature flag. Primary hub entry moves to `/development`; no `/academy` command.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `player_engine` (youth_intake, youth_math, potential), `economy.facility_effects`, `gacha.generator`, discord.py hubs/views, APScheduler intake/growth jobs, `apply_club_economy`, existing academy RPCs from migrations 042/060/075/088

**Storage**: Supabase — extend `player_cards` + `players` / weekly ledger; rework scout assessment vs shortlist tables; `game_config` balance keys; migration **095** (schema + RPCs + cutover) — optional **096** only if VALIDATE/CHECK split needed post-repair. Repo head today: **094**.

**Testing**: pytest for rarity weights/bands, range narrowing monotonicity, slot caps 3/3/4/4/5, weekly ledger, star-from-interval, facility preview math; SQL parity for caps/slot helpers; RPC smoke via scratch apply + `verify_required_schema.sql`

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo gameplay redesign (packages + discord_bot + migrations)

**Performance Goals**: Monday intake remains per-manager loop with seating inside one RPC; daily growth stays set-based single RPC; scout dispatch/finalize under Discord defer window; cutover is one-shot migration/ops batch, not hub hot path

**Constraints**: AGENTS.md monorepo/state/DB rules; no `discord` in `packages/`; no XP/coin bypasses; columns/RPCs only via new migrations; FR-022 — do not trust bot-submitted rarity/POT as SoT; no `/academy`; no second player table; Legendary kill switch via config; YAGNI — no youth matches/coaches/pity/pre-promote trading

**Scale/Scope**: ~1–2 migrations; V2 generation + scout-range math modules; academy hub + Development/Squad entry + facilities preview; cutover + flag; tests + `change_log.md`; reconcile `.specify/specs/v1.0.0/` on implement

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Generation/range/growth math in `packages/`; hubs/embeds/tasks in `apps/discord_bot/` |
| II. DB via RPC / atomic economy | PASS | Intake/assess/discover/promote/release/growth/cutover via RPCs; fees via `apply_club_economy` |
| III. Typing / Pydantic | PASS | Typed generation + range helpers; Pydantic at package boundaries |
| IV. Slash + defer | PASS | No new slash; Development/Squad/Profile buttons defer immediately |
| V. APScheduler | PASS | Reuse Monday intake + daily growth; age-out/grace on growth or season aging — no speculative jobs |
| VI. Friendly errors | PASS | Map capacity/weekly-cap/scout conflicts to ephemeral copy |
| VII. YAGNI | PASS | Rebalance 015 surfaces; no parallel academy product or `/academy` |

**Post-Phase 1 re-check**: PASS — dual scout products (assessment + discovery) justified in research as the only way to satisfy US-3 and FR-016 together; server re-validation (not full SQL card factory) is the ponytail FR-022 path with a documented upgrade.

## Project Structure

### Documentation (this feature)

```text
specs/051-youth-academy-rarity/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── rarity-generation-v2.md
│   ├── scout-assessment-ranges.md
│   ├── weekly-actions-ledger.md
│   ├── capacity-cutover.md
│   └── academy-hub-surfaces.md
└── tasks.md                # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
# Schema / RPCs
supabase/migrations/095_youth_academy_rarity_v2.sql   # NEW — columns, configs, RPCs, cutover, guards
supabase/scripts/verify_required_schema.sql           # extend tables/columns/functions/policies
scratch/apply_migration_095.py                        # NEW — follow existing apply pattern

# Pure logic
packages/economy/economy/facility_effects.py          # ACADEMY_SLOT_CAPS 3/3/4/4/5; rarity weights; preview effects
packages/player_engine/player_engine/youth_intake.py  # V2 rarity-first generation; intake default 2
packages/player_engine/player_engine/youth_math.py     # growth speed by level; star_band from interval; ready advisory by level
packages/player_engine/player_engine/scout_ranges.py   # NEW — init bounds, narrow by tier, monotonicity
packages/player_engine/player_engine/potential.py      # reuse rarity_potential_cap / clamp / validate
packages/gacha/gacha/generator.py                     # wrap V2 intake/discovery payloads
packages/*/__init__.py                                # exports

# Discord
apps/discord_bot/views/academy_hub.py                 # ranges not exact POT; assess + discover; weekly counters; origin-aware back
apps/discord_bot/embeds/academy_embeds.py              # range/stars/readiness; graduation embed; over-capacity line
apps/discord_bot/embeds/youth_intake_embeds.py         # no exact POT dump; range + rarity
apps/discord_bot/cogs/development_cog.py               # primary Youth Academy button
apps/discord_bot/cogs/squad_cog.py                     # optional Youth + compact status
apps/discord_bot/cogs/profile_cog.py                   # keep Manage Academy compatibility; compact status
apps/discord_bot/views/store_facilities.py             # before→after capacity/odds/range/growth preview
apps/discord_bot/tasks/youth_intake_notifier.py         # count=2; V2 generate; respect flag
apps/discord_bot/tasks/academy_growth_job.py           # growth + age-out grace/auto-release; finalize assessments
apps/discord_bot/core/api_errors.py                   # map new RPC errors
apps/discord_bot/main.py / core/scheduler_jobs.py      # no new slash; jobs unchanged schedule unless aging hook needs it

# Tests / ops / copy
tests/test_academy_slots.py                           # update caps
tests/test_youth_math.py                              # growth / stars-from-interval
tests/test_youth_intake_v2.py                         # NEW — rarity ceilings + L5 legendary rate / kill switch
tests/test_scout_ranges.py                            # NEW — narrow/monotonic/contain true POT
tests/test_academy_weekly_ledger.py                   # NEW — promote/sign caps
change_log.md                                         # player-facing YA V2
.specify/specs/v1.0.0/spec.md + plan.md               # reconcile on implement (SDD rule)
```

**Structure Decision**: Extend Feature 015’s `in_academy` card flag and hub — do not introduce `academy_players`. Split scout UX into **assessment** (per seated prospect) and **discovery** (paid add under capacity/ledger). Generation stays Python with RPC **re-validation** (FR-022 ponytail); full SQL generator deferred. Agent-context update script absent — skipped (same as 048/049).

## Complexity Tracking

| Choice | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| Assessment + discovery scout | US-3 ranges + FR-016 paid signing | Assessment-only drops paid acquisition; shortlist-only leaks exact POT and skips range UX |
| Columns on `player_cards` for bounds | Persist visible interval per prospect | Encode only in Discord state — lost on restart / multi-device |
| Weekly ledger table/columns | Enforce promote/sign caps atomically | App-only counters — raceable double-taps |
| Feature flag + cutover in 095 | Live clubs need repair/grandfather | Big-bang without flag risks illegal generation mid-deploy |
| Python generate + RPC validate | FR-022 without rewriting card factory in SQL | Trust bot JSON — fails FR-022; full SQL factory is large YAGNI |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Implementation sketch (for `/speckit.tasks`)

### P0 — Integrity + capacity + intake

1. Pure V2 generation (rarity weights by YA level, bands within caps, Legendary L5-only + kill switch); default intake count 2; update `ACADEMY_SLOT_CAPS` / SQL `academy_slot_cap`.
2. Migration **095** (partial): config keys, slot helper, intake RPC seating against new cap, integrity asserts, feature flag `youth_academy_v2_enabled`.
3. Unit tests for ceilings + slot curve + intake seating math.

### P1 — Scout ranges + weekly ledger + growth/age-out

4. Columns: visible POT bounds, assessment level, academy origin, age-out pending; `academy_weekly_actions` ledger.
5. Assessment RPCs (dispatch/finalize/narrow) + discovery rebalance under signing cap; promote weekly cap + optional fee.
6. Growth never past POT/cap; aging warn → ≤1 POT decay → grace → auto-release (replace force-promote-or-delete).
7. Cutover: repair illegal academy POT; init ranges containing true POT; grandfather over-capacity; RLS + verify guards.

### P2 — Surfaces + rollout

8. Development primary Youth button; Squad optional; Profile compatibility; origin-aware back; graduation embed; facilities before→after preview; remove exact POT from Deep/list defaults; stars from interval.
9. Wire jobs behind flag; monitoring counters/logs; Legendary kill switch documented; `change_log.md` + SDD reconcile.
10. Acceptance: SC-001…SC-010 via quickstart scenarios.

### Explicit non-goals

`/academy` command; second player table; youth currency/coaches/matches/loans/pity; pre-promotion trading; 7-day post-promote trade lock (deferred); automatic rarity upgrades to preserve illegal POT.

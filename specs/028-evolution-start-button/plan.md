# Implementation Plan: Evolution Start Button Fix

**Branch**: `028-evolution-start-button` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-evolution-start-button/spec.md`

## Summary

Fix Evolution Command Center **Start New Evolution** staying greyed out after the live cold-start cooldown has elapsed, and fix stale start-cost copy on the same screen.

**Root cause**: `get_evolution_hub_status` (migration 023 only) hardcodes `cooldown_hours = 10` and `coin_multiplier = 10`, while `start_player_evolution` (046/062) reads `game_config` (`evolution_cooldown_hours` seeded **6**, costs `500 + 5×OVR`). The hub disables the Start button from hub status, so managers see a false ~4h lockout after the real 6h window. Live player evidence: `0/3` slots + `9h 23m` remaining implies ~37m since last start on a **10h** clock.

**Approach**: One forward migration redefining `get_evolution_hub_status` to use the same `get_game_config_int` keys as start; align hub Resources cost string with package constants; keep intentional disable for full slots / real cooldown; small pytest + verify; `change_log.md` note. No new slash commands or tables.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: Existing Discord bot (`discord.py`), Supabase RPCs, `player_engine.evolution_tracks` constants

**Storage**: Existing `players.last_evolution_started_at`, `active_evolutions`, `game_config` keys — no new columns

**Testing**: pytest (`tests/test_evolution_gate.py` + cost-copy / status-shape helpers if added); SQL apply + `verify_required_schema.sql`; manual hub open

**Target Platform**: Discord bot + hosted Supabase

**Project Type**: Monorepo bugfix (RPC + hub UI honesty)

**Performance Goals**: Single existing hub RPC call; no extra round-trips

**Constraints**: AGENTS.md — no Discord in packages; new numbered migration only (do not edit 023 in place on remote); no new slash/hub surfaces; economy/progression via existing RPCs; defer already on hub entry; reconcile `.specify/specs/v1.0.0/` if AC drifts; brief `change_log.md`

**Scale/Scope**: ~1 migration + cog string + tests + changelog; optional scratch apply script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | UI/cost copy in `apps/discord_bot`; package constants already exist — no Discord in packages |
| II. DB via RPC | PASS | Fix inside `get_evolution_hub_status`; no cog UPDATE loops; no new financial mutation path |
| III. Typing | PASS | Existing typed helpers; no new cross-boundary models required |
| IV. Slash + defer | PASS | Existing `/development` Evolutions; `safe_defer` already on hub show |
| V. APScheduler | N/A | No scheduler change |
| VI. Friendly errors | PASS | Gate messages already ephemeral; disabled button relies on embed copy (FR-004) |
| VII. YAGNI | PASS | Align existing RPC+copy; no new commands, tables, or cooldown redesign |

**Post-Phase 1 re-check**: PASS — contracts stay on existing RPC JSON shape with additive cost fields; no constitution violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/028-evolution-start-button/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── get-evolution-hub-status.md
│   └── evolution-hub-start-cost-copy.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
supabase/migrations/073_evolution_hub_status_config.sql   # NEW — REPLACE get_evolution_hub_status
scratch/apply_migration_073.py                            # NEW (ops pattern)
supabase/scripts/verify_required_schema.sql               # confirm function still guarded (no new objs expected)

apps/discord_bot/cogs/development_cog.py                  # Resources cost string; prefer status fields if present

packages/player_engine/player_engine/evolution_tracks.py  # already mirrors 6h / 500+5×OVR — verify only

tests/test_evolution_gate.py                              # extend if gate/copy helpers change
tests/test_evolution_hub_copy.py                          # NEW small: cost formula string / constants

change_log.md                                             # player-facing note
.specify/specs/v1.0.0/spec.md + plan.md                   # brief reconcile on implement
```

**Structure Decision**: Smallest fix is migration-align hub status with start RPC config, then one hub embed string. No new Discord surfaces; no package Discord imports.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **Migration 073**: `CREATE OR REPLACE FUNCTION public.get_evolution_hub_status(p_owner_id BIGINT)` — replace hardcoded constants with:
   - `evolution_max_active` (default 3)
   - `evolution_cooldown_hours` (default **10** to match `start_player_evolution` fallback; live seed is 6)
   - `evolution_start_energy`, `evolution_start_flat`, `evolution_start_ovr_mult`
   - Keep replacement / `can_start` / `can_cold_start` / `can_replace` semantics identical
   - Return additive JSON keys `start_coin_flat`, `start_coin_ovr_mult` (keep `start_coin_multiplier` as ovr mult for back-compat, now sourced from config not 10)
   - Prefer `sync_action_energy` + `action_energy` for Resources energy if cheap parity with start; else keep dual-written `training_energy` if already correct in prod — decide in tasks from 028/046 dual-write reality (do not break energy display)
2. **Cog**: Replace ``10×OVR`` Resources line with ``{flat}+{mult}×OVR`` using package constants or status fields; keep button `disabled=not can_start` logic (intentional).
3. **Tests**: Assert package cost constants match documented formula; assert gate still blocks full slots / cooldown seconds; optional SQL smoke that hub remaining uses config hours.
4. **Verify**: Apply 073; run `verify_required_schema.sql`; reopen Evolution hub — after real 6h, button enables; during cooldown, timer ≤6h window.
5. **Out of scope**: Changing cooldown length product rule; new tracks; making disabled buttons clickable; fixing stale ephemeral after view timeout; redesigning cancel/replacement.

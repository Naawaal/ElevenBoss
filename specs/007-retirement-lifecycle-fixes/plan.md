# Implementation Plan: Retirement Lifecycle Fixes

**Branch**: `007-retirement-lifecycle-fixes` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-retirement-lifecycle-fixes/spec.md`

## Summary

Three surgical fixes to the existing DOB-based retirement pipeline: (1) expand veteran decline so **DRI** decays from 33+ and **SHO** from 35+ (closing immortal-finisher / immortal-dribbler exploits); (2) on retirement, **auto-promote** a same-role reserve into the vacated starting slot, or set **`players.squad_invalid`** and block match starts with clear `/squad` guidance; (3) rewrite regen rarity weights so ≥85 OVR legends never spawn Common prospects.

**Technical approach**: Forward migration `053` replaces `process_season_aging` / `retire_player_card` / `set_formation_and_assignments` (clear flag); mirror decline + rarity in `player_engine`; battle middleware reads `squad_invalid` for copy. No new tables, slash commands, or hubs.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: pydantic ≥2.0, discord.py ≥2.7, supabase async client, local `player_engine` / `match_engine`

**Storage**: Supabase Postgres — column `players.squad_invalid BOOLEAN NOT NULL DEFAULT FALSE`; replace RPCs `retire_player_card`, `process_season_aging`, `set_formation_and_assignments` (clear flag on valid XI save). Reuse existing `formation_slot_role()`.

**Testing**: pytest — `yearly_stat_decline` bands; regen rarity distribution; optional pure helper for rarity weights

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — pure package math + SQL RPC mutations + thin Discord gate

**Performance Goals**: Retirement vacancy resolution inside the same RPC transaction as delete/retire; no extra Discord round-trips for auto-promote; battle gate is one column read (or already-fetched player row)

**Constraints**: AGENTS.md — no `discord` in `packages/`; columns/RPCs only via new migration (never edit 041 in place on remote); extend verify guards; no new slash commands/tables; `change_log.md` on ship; reconcile `.specify/specs/v1.0.0/` AC-31d / AC-34 on implement

**Scale/Scope**: ~10–14 files; 1 migration; pure decline + rarity updates; battle copy + squad save clear; tests for math

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Decline/rarity stay in `player_engine`; battle/squad in `apps/` |
| II. DB mutations via RPC | PASS | Auto-promote + `squad_invalid` inside `retire_player_card`; aging still one batch RPC |
| III. Typing / Pydantic at boundaries | PASS | Existing card models; rarity helper typed |
| IV. Slash + defer | PASS | No new slash; existing battle/squad defer paths |
| V. APScheduler | PASS | No new jobs; Monday aging + regen spawn unchanged |
| VI. User-friendly errors | PASS | Retirement-aware squad-invalid message; no raw exceptions |
| VII. YAGNI | PASS | No new table; reuse `formation_slot_role`; no squad UI redesign |

**Post-Phase 1 re-check**: PASS — contracts cover decline math, retire vacancy RPC, battle gate, regen rarity; additive column only; Python mirror aligned with SQL.

## Project Structure

### Documentation (this feature)

```text
specs/007-retirement-lifecycle-fixes/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── aging-decline-curve.md
│   ├── retire-squad-vacancy-rpc.md
│   ├── battle-squad-invalid-gate.md
│   └── regen-rarity-weights.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/
├── age_manager.py           # MODIFY — yearly_stat_decline: DRI@33+, SHO@35+; align PAS/DEF@33+
├── regen_pool.py            # MODIFY — rarity bands from peak OVR
└── __init__.py              # MODIFY if new rarity helper exported

apps/discord_bot/
├── cogs/battle_cog.py       # MODIFY — squad_invalid / retirement copy on XI gate (bot, league, friendly)
├── cogs/squad_cog.py        # OPTIONAL — surface invalid banner on hub if flag set
└── (no new cog)

supabase/migrations/
└── 053_retirement_lifecycle_fixes.sql   # NEW — column + RPC replaces + guard

supabase/scripts/verify_required_schema.sql  # EXTEND — players.squad_invalid column

tests/
├── test_age_manager.py      # EXTEND — DRI/SHO decline bands + PAS/DEF@33
└── test_regen_pool.py       # EXTEND — rarity weights by OVR band (seeded)

scratch/apply_migration_053.py   # NEW — apply pattern
change_log.md                    # MODIFY on ship
.specify/specs/v1.0.0/spec.md + plan.md  # RECONCILE AC-31d / regen rarity on implement
```

**Structure Decision**: Keep aging/rarity formulas in `player_engine` (already mirrored). Persist vacancy repair + invalid flag only in SQL RPCs. Discord only improves the match gate message and optionally shows an invalid hint on `/squad`.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Notes (for `/speckit.tasks`)

1. **Decline order (per advanced year `A`)** — Match SQL loop to Python `yearly_stat_decline(A)`:
   - `A >= 31`: PAC −1 (or −2 if `A >= 35`), PHY same
   - `A >= 33`: PAS −1, DEF −1, **DRI −1**
   - `A >= 35`: **SHO −1**
   - Floor all at 1; `recalculate_card_ovr` after each year (existing)
2. **Python bugfix in-scope** — Current `yearly_stat_decline` for VETERAN (31–34) omits PAS/DEF at 33–34; SQL already applies them. Align Python to SQL while adding DRI/SHO.
3. **Auto-promote** — Inside `retire_player_card`: capture `position_slot` before DELETE; after retire, if slot was set, pick highest-`overall` then lowest-`id` owned non-retired reserve whose `position = formation_slot_role(formation, slot)` and not already in `squad_assignments`; INSERT; else `UPDATE players SET squad_invalid = TRUE`. If XI count returns to 11, set `squad_invalid = FALSE`.
4. **Clear flag** — Auto-clear when promote restores 11; also `set_formation_and_assignments` after writing 11 assignments successfully sets `squad_invalid = FALSE`.
5. **Battle gate** — Prefer reading `players.squad_invalid` (or count≠11); if invalid/hole: *"Your starting XI is invalid due to a recent retirement. Please visit `/squad` to set your lineup."* Keep count≠11 as hard stop even if flag stale.
6. **Regen** — Extract `regen_rarity_for_ovr(ovr, rng) -> str` with exact FR-014 weights; keep OVR/age/position bands unchanged.
7. **Migration** — `053_…sql`; DROP/replace function overloads as needed; extend verify for `column:public.players.squad_invalid`.
8. **Out of scope** — New slash commands, new tables, dual-position matrix, marketplace UI redesign, changing retirement age / DOB math, injury-aware auto-promote filtering.

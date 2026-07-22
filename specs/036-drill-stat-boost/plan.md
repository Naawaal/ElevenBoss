# Implementation Plan: Drill Attribute Boost

**Branch**: `036-drill-stat-boost` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/036-drill-stat-boost/spec.md`

## Summary

Restore a modest focused payoff on Stat Training Drills: each completed drill still grants XP (and still costs energy/coins / daily slots), and **also attempts `+1` on the drill’s mapped attribute** (PAC/SHO/PAS/DRI/DEF/PHY). If the attribute is at 99 or the projected overall would exceed potential, **skip the attribute write**, still complete the drill for XP/costs, and return an explicit block reason for the hub summary.

**Approach**: One forward migration (`078`) that `CREATE OR REPLACE`s `process_stat_drill` — map `p_drill_id` → stat column (already in catalog), **pre-check** with existing `peek_card_ovr` (same ceiling rules as skill allocation), optionally `UPDATE` + `recalculate_card_ovr`, always keep `apply_club_economy` + `apply_card_xp`. Extend RPC JSON + `parse_stat_drill_result` + Training Drills select/summary copy. Reuse `can_allocate_skill_point` for UI preview. Update AGENTS / v1.0.0 SDD / `change_log.md` that still say “XP only”. No new tables, slash commands, or drill types.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: Existing Discord bot (`discord.py`), Supabase RPCs (`process_stat_drill`, `apply_card_xp`, `apply_club_economy`, `peek_card_ovr`, `recalculate_card_ovr`, `assert_card_action_allowed`), `player_engine` (`DRILL_CATALOG`, `can_allocate_skill_point`, `drill_xp_reward`)

**Storage**: Existing `player_cards` attribute columns + `overall` / `potential`; no new columns or tables. Behavior change only inside `process_stat_drill` (+ client parsing/UI).

**Testing**: pytest for pure gate/preview helpers + parser shape; migration source/contract greps; optional scratch smoke applying 078; manual Training Drills run

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo progression UX change (RPC + hub UI + pure preview reuse)

**Performance Goals**: One extra read/peek inside the existing drill transaction; no extra Discord round-trips beyond today’s single RPC

**Constraints**: Constitution + AGENTS — no Discord in packages; atomic RPC mutation; new numbered migration only (do not edit 075 in place on remote); preserve US-42.2 `assert_card_action_allowed(..., 'drill')`; no new slash/hub surfaces; XP still via `apply_card_xp`; coins/energy via `apply_club_economy`; reconcile SDD + AGENTS “XP only” wording; brief `change_log.md`

**Scale/Scope**: ~1 migration + drill_rpc parser + development_cog Training Drills copy + small tests + docs; optional scratch apply/smoke

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Cap preview helpers stay in `packages/player_engine`; Discord copy in `apps/discord_bot` |
| II. DB via RPC | PASS | Attribute + OVR writes only inside `process_stat_drill`; no cog-level `UPDATE player_cards` |
| III. Typing / Pydantic | PASS | Extend existing dict parser; reuse typed `can_allocate_skill_point` |
| IV. Slash + defer | PASS | Existing `/development` Training Drills; defer already on run |
| V. APScheduler | N/A | No scheduler change |
| VI. Friendly errors | PASS | Soft-fail boost returns reason in JSON; hard failures stay existing exceptions |
| VII. YAGNI | PASS | Reuse `peek_card_ovr` / catalog / allocation gates; no new drill catalog or commands |

**Post-Phase 1 re-check**: PASS — contracts add additive JSON fields only; soft-fail boost avoids allocate-style whole-txn raise; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/036-drill-stat-boost/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── process-stat-drill-boost.md
│   └── drill-hub-stat-copy.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/078_drill_stat_boost.sql          # NEW — REPLACE process_stat_drill
scratch/apply_migration_078.py                        # NEW (ops pattern)
scratch/smoke_drill_stat_boost_078.py                 # OPTIONAL smoke
supabase/scripts/verify_required_schema.sql           # confirm process_stat_drill still guarded

packages/player_engine/player_engine/drill_catalog.py # already maps drill→stat (verify only)
packages/player_engine/player_engine/progression_gates.py  # reuse can_allocate_skill_point / can_gain_stat_progression
packages/player_engine/player_engine/__init__.py       # export only if new thin helper added

apps/discord_bot/core/drill_rpc.py                    # parse boost / block fields
apps/discord_bot/cogs/development_cog.py              # select preview + post-drill summary

tests/test_drill_stat_boost.py                        # NEW — parser + preview gate cases
tests/test_progression_caps.py                        # extend if shared gate behavior touched

change_log.md                                         # player-facing note
AGENTS.md                                             # amend “drills grant XP only”
.specify/specs/v1.0.0/spec.md + plan.md               # amend AC-23f / XP-only wording on implement
```

**Structure Decision**: Keep enforcement in SQL (single RPC), preview/copy in the existing Training Drills view, pure package only for gate/preview mirrors already present. No new Discord surface.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **Migration 078** — Base body from latest `process_stat_drill` in **075** (with `assert_card_action_allowed(..., 'drill')`). After cost/cap gates and **before** economy charge (or immediately after charge but before XP — prefer: eligibility peek → charge → optional stat write → XP):
   - Map `p_drill_id` → `v_stat_col` (`pac_sprint`→`pac`, …).
   - `SELECT` locked card fields including the target stat, `overall`, `potential`, `position`.
   - Soft-fail path (do **not** `RAISE` for pot/99):
     - If `stat >= 99` → `stat_boosted=false`, reason e.g. `stat_at_maximum`
     - Else if `overall >= potential` → `stat_boosted=false`, reason e.g. `at_potential`
     - Else `peek_card_ovr(card, col, stat+1)`; if `> potential` → blocked `would_exceed_potential`
     - Else `UPDATE` +1 on column, `recalculate_card_ovr`, `stat_boosted=true`
   - Always run existing economy + daily counters + `apply_card_xp`.
   - Return additive keys (keep existing `xp_gain` / `progression` / `economy`): `stat_boosted`, `stat`, `stat_delta`, `new_stat_value`, `new_ovr`, `boost_block_reason` (null when boosted).
2. **Do not** copy `allocate_skill_point`’s apply-then-`RAISE` pot check — that would roll back XP/coins. Soft-fail only.
3. **Parser**: `parse_stat_drill_result` exposes boost fields with safe defaults for old payloads.
4. **UI**: Drill option descriptions include `+1 XXX` when `can_allocate_skill_point` allows, else a short capped hint; summary shows boost or block reason; remove unconditional “OVR unchanged — spend skill points…” when boost applied (still mention Allocate Skills when blocked / unchanged OVR).
5. **Docs**: AGENTS §7 drills bullet + v1.0.0 AC-23f + `change_log.md`.
6. **Out of scope**: Multi-stat drills; changing 20/5 caps; spending skill points on drills; Recover/fusion/evolution changes; new slash commands.

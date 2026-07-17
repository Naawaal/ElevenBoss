# Implementation Plan: Development Hub Recovery

**Branch**: `023-dev-hub-recovery` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-dev-hub-recovery/spec.md`

## Summary

Relocate **Active Recovery Sessions** out of Training Drills onto a dedicated **Recover** button on the main `/development` hub. Managers multi-select **1–3** eligible roster players, confirm total energy cost, and apply the existing fatigue grant (**+40** default, **5⚡** per player) with **0 XP / 0 coins**. Training Drills become skill-only. Recovery **stops consuming skill-drill daily slots** (energy-gated only). Atomic batch RPC ensures all-or-nothing energy + fatigue for the selection.

**Technical approach**: (1) Migration `066` — `process_recovery_batch` + rewrite `process_recovery_session` without drill-cap side effects (thin single-card wrapper or DROP after grepping callers); (2) strip Recovery from `StatDrillView` / training copy; (3) new Recover select → confirm → result flow on `DevelopmentHubView` (Mentor-style); (4) pure eligibility/cost helpers + tests; (5) `change_log` + SDD reconcile.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+

**Primary Dependencies**: discord.py, Supabase async client, `player_engine.fatigue`, existing `apply_club_economy` / `sync_action_energy`

**Storage**: Supabase Postgres — no new tables; reuse `game_config` keys `fatigue_recovery_energy` (5) and `fatigue_recovery_session` (40); new/replaced RPCs only

**Testing**: pytest — eligibility filter, batch energy math, clamp; optional scratch smoke for batch RPC

**Target Platform**: Discord bot + hosted Supabase

**Project Type**: Monorepo UX relocation (hub button + RPC batch; no new slash command)

**Performance Goals**: One RPC per Recover confirm (1–3 cards); Discord defer before DB

**Constraints**: AGENTS.md — no Discord in packages; fatigue/energy only via RPC; all-or-nothing batch (FR-009); exclude injured / in-hospital; no drill-slot consumption (FR-012); Ponytail — move, don’t invent new recovery systems

**Scale/Scope**: ~8–12 files; 1 migration; Development hub + drills cleanup only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Eligibility/cost pure in `packages/`; Discord views in `apps/discord_bot/` |
| II. DB via RPC | PASS | Batch recover via `process_recovery_batch`; economy via `apply_club_economy` |
| III. Typing | PASS | Typed helpers; explicit JSON contracts |
| IV. Slash + defer | PASS | No new slash; Recover callbacks defer immediately |
| V. APScheduler | PASS | Untouched (`process_daily_recovery` unchanged) |
| VI. Friendly errors | PASS | Map batch errors in `api_errors.py`; Hospital copy updated |
| VII. YAGNI | PASS | Relocate + batch 1–3; no physio SKU, no auto-recover job, no new command |

**Post-Phase 1 re-check**: PASS — single atomic batch RPC preferred over N sequential single-card calls (would violate all-or-nothing on mid-batch failure). Keep transfer-list + active-evolution gates from today’s single-card RPC (existing safety, not new product scope).

## Project Structure

### Documentation (this feature)

```text
specs/023-dev-hub-recovery/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── process-recovery-batch-rpc.md
│   ├── development-recover-ui.md
│   └── drills-recovery-removal.md
└── tasks.md             # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/066_dev_hub_recovery.sql
scratch/apply_migration_066.py
supabase/scripts/verify_required_schema.sql          # EXTEND — process_recovery_batch

packages/player_engine/player_engine/fatigue.py      # MODIFY — recovery_eligible, batch energy helper
packages/player_engine/player_engine/__init__.py      # EXPORT

apps/discord_bot/cogs/development_cog.py             # MODIFY — hub Recover; strip drills Recovery
apps/discord_bot/core/api_errors.py                  # MODIFY — batch / Hospital copy
change_log.md                                        # player-facing note
.specify/specs/v1.0.0/spec.md                        # reconcile Development Recover surface

tests/test_fatigue_injury_math.py                    # EXTEND — eligibility + batch energy
# optional: tests/test_recovery_batch_math.py if helpers grow

# CLEANUP (grep zero):
#   RECOVERY_DRILL_ID, "Recovery Session" in StatDrillView / training embed,
#   process_recovery_session callers outside new path (or keep as 1-card wrapper)
```

**Structure Decision**: Keep formulas in `player_engine`. Persist only through RPCs. Discord is a thin deferred UI over `process_recovery_batch`, mirroring Mentor Transfer’s select → confirm → hub refresh. Training Drills lose all Recovery branches.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **Migration `066`**: Add `process_recovery_batch(p_owner_id BIGINT, p_card_ids UUID[])` — validate length 1–3, lock club, validate every card, charge `N × fatigue_recovery_energy` once, apply fatigue to each, return per-card results + totals. **Do not** touch `daily_drill_count` / `player_drill_daily_log`. Rewrite or wrap `process_recovery_session` so it also skips drill caps (or DROP after UI removal + grep). Extend verify guards.
2. **Drills cleanup**: Remove `RECOVERY_DRILL_ID`, Recovery select option, recovery run branch, recovery config fetches used only for drills copy; rewrite training embed to skill-only.
3. **Hub UI**: `DevelopmentHubView` button **💚 Recover** → multi-select (`min_values=1`, `max_values=3`) → confirm embed → RPC → success + `show_hub`.
4. **Eligibility UI filter**: not retired, not academy, not injured, not in_hospital, fatigue &lt; 100; also hide transfer-listed / active-evo (RPC will reject anyway).
5. **api_errors**: Update Hospital message to say Recover / Development hub, not “Training Drills”; add batch validation messages (`Select 1 to 3 players`, etc.).
6. **Rollback**: Revert migration RPCs (or re-apply prior `process_recovery_session` body from 062); restore drills Recovery UI from git; remove hub Recover button. Hospital/passive untouched.
7. **Out of scope**: New slash, Store physio, passive TG math, Hospital curves, &gt;3 players, auto-recover jobs.

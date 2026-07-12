# Implementation Plan: Active Fatigue Recovery

**Branch**: `009-fatigue-recovery` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-fatigue-recovery/spec.md`

## Summary

Give managers agency over fitness: a **Recovery Session** on `/development` Training Drills restores fatigue (+40 default) for Basic-drill energy and a shared drill slot, with **0 XP / 0 coins**. Scale daily passive fatigue by **Training Ground** level (`15 + TG×5`). Keep bench rest, match drain, Hospital, and penalty tiers unchanged. Physio Store consumables stay out of scope.

**Technical approach**: (1) Pure helpers in `player_engine/fatigue.py`; (2) migration `054` — `process_recovery_session` RPC + TG-aware `process_daily_recovery` + `game_config` seeds; (3) Development Training Drills UI branch for Recovery vs skill; (4) `api_errors` + tests; (5) reconcile spec FR-004 (drills are instant, not 4h). Deploy migration + verify before bot UI.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: pydantic ≥2.0, discord.py ≥2.7, supabase async client, local `player_engine`

**Storage**: Supabase Postgres — no new tables; replace `process_daily_recovery` body; add `process_recovery_session`; `game_config` keys

**Testing**: pytest — `tests/test_fatigue_injury_math.py` (TG passive + recovery session clamp)

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — pure package math + Discord UI + SQL RPC

**Performance Goals**: Single RPC per Recovery Session; one set-based daily recovery UPDATE (join TG); Discord defer before DB

**Constraints**: AGENTS.md — no `discord` in `packages/`; no XP/coin bypasses; columns/RPCs only via migrations; extend `/development` only; no new slash command; verify schema before bot ship; `change_log.md` on ship; reconcile `.specify/specs/v1.0.0/` on implement; YAGNI — no async drill jobs

**Scale/Scope**: ~8–12 files; 1 migration; fatigue.py + Development UI; scheduler caller unchanged

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Math in `fatigue.py`; UI in `development_cog` |
| II. DB mutations via RPC | PASS | `process_recovery_session` + `process_daily_recovery`; economy via `apply_club_economy` |
| III. Typing / Pydantic at boundaries | PASS | Pure int helpers; RPC JSON mapped in bot |
| IV. Slash + defer | PASS | No new slash; Recovery callbacks defer immediately |
| V. APScheduler | PASS | Existing `daily_recovery_job` only |
| VI. User-friendly errors | PASS | New messages → `api_errors` |
| VII. YAGNI | PASS | Instant Recovery (no job table); no physio SKU; no TG schema 0 |

**Post-Phase 1 re-check**: PASS — contracts cover RPC, daily TG math, UI, pure helpers; no new tables; XP pipe untouched.

## Project Structure

### Documentation (this feature)

```text
specs/009-fatigue-recovery/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── process-recovery-session-rpc.md
│   ├── daily-recovery-tg.md
│   ├── development-recovery-ui.md
│   └── fatigue-recovery-math.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/
├── fatigue.py                 # MODIFY — passive_recovery_amount, apply_recovery_session, TG-aware apply_passive_recovery
└── __init__.py                # MODIFY — export new helpers/constants

apps/discord_bot/
├── cogs/development_cog.py    # MODIFY — Recovery Session choice in Training Drills
├── core/api_errors.py         # MODIFY — rested / injured recovery messages
└── core/scheduler_jobs.py     # NO CHANGE (already calls process_daily_recovery)

supabase/migrations/
└── 054_fatigue_recovery.sql   # NEW — config, process_recovery_session, process_daily_recovery, guards

supabase/scripts/verify_required_schema.sql  # EXTEND — function:process_recovery_session

tests/
└── test_fatigue_injury_math.py  # MODIFY — TG passive + recovery session

scratch/apply_migration_054.py   # NEW — apply pattern
change_log.md                    # MODIFY on ship
AGENTS.md / .agents/AGENTS.md    # MODIFY on ship — recovery note under fatigue/US-39
.specify/specs/v1.0.0/spec.md + plan.md  # RECONCILE on implement (US-39 extension)
specs/009-fatigue-recovery/spec.md       # RECONCILE FR-004 → instant
```

**Structure Decision**: Keep formulas in `player_engine` (stateless). Persist only through RPCs. Discord stays a thin deferred UI over `process_recovery_session`, mirroring skill drills under Training Drills.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Notes (for `/speckit.tasks`)

1. **Instant, not 4h** — Research R1: reconcile spec FR-004 before or during implement.
2. **Constants** — Mirror SQL/`game_config`: recovery 40, energy 10, passive base 15, TG per level 5; TG schema min 1 → daily 20 at L1.
3. **RPC order** — See [contracts/process-recovery-session-rpc.md](./contracts/process-recovery-session-rpc.md); never `apply_card_xp`.
4. **Daily recovery** — Set-based UPDATE joining `players.training_ground_level`; hospital branch unchanged.
5. **UI** — After player select, branch Skill vs Recovery; always `defer` first; short-lived views.
6. **Grep** — Callers of `process_daily_recovery`, `apply_passive_recovery`, `FATIGUE_PASSIVE_PER_DAY`, Development drill handlers.
7. **Out of scope** — Physio consumables, drain/penalty changes, Hospital UI, new slash commands, async job infra.

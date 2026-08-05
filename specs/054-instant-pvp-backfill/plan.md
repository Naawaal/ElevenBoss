# Implementation Plan: Feature 054 — Instant PvP Backfill and Ghost Managers

**Branch**: `054-instant-pvp-backfill` | **Date**: 2026-08-05 | **Spec**: [spec.md](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/054-instant-pvp-backfill/spec.md)

**Input**: Feature specification from `/specs/054-instant-pvp-backfill/spec.md`

## Summary

Solves low-population PvP queue failures by introducing a three-level opponent-selection hierarchy (Live Human -> Ghost Manager -> Calibrated Ranked AI) within a guaranteed 15-second matchmaking window. A searching manager searches for a live human opponent for 10 seconds; if none is available, the system atomically claims a recent frozen squad snapshot of another real manager (Ghost Manager) or generates a division-calibrated AI opponent. Ghost matches are executed single-sidedly, preserving 100% on-demand Ranked PvP availability without offline manager penalty or LP corruption.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `discord.py` (>=2.7.0), `supabase` (async, >=2.0.0), `pydantic` (>=2.0.0), `apscheduler` (>=3.10.0)
**Storage**: Supabase (PostgreSQL 15+) via migrations (`103_instant_pvp_backfill.sql`) and stored procedure RPCs
**Testing**: `pytest`
**Target Platform**: Linux / Windows Discord Bot Service
**Project Type**: Python Monorepo (`apps/discord_bot` + `packages/`)
**Performance Goals**: Match queue search-to-kickoff under 15s (median <=10s) for 95% of entries
**Constraints**: Zero imports of `discord` inside `packages/`; single-sided finalization for Ghost/AI matches; atomic database locks (`FOR UPDATE SKIP LOCKED`)
**Scale/Scope**: Up to 10k active managers, automatic 7-day ghost snapshot retention

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: Monorepo Architecture**: PASS. `packages/pvp` contains pure stateless match selection & reward multiplier logic with zero `discord` imports. All Discord cogs, embeds, views, and stadium rendering live in `apps/discord_bot/`.
- **Principle II: Database & Atomic RPCs**: PASS. `try_match_pvp_queue`, `refresh_pvp_ghost_snapshot`, and `finalize_pvp_match` handle all queue, snapshot, and finalization mutations in atomic PostgreSQL transactions.
- **Principle III: Strict Typing & Pydantic**: PASS. Pydantic models in `packages/pvp` represent ghost snapshots and encounter structures crossing package boundaries.
- **Principle IV: Discord Interaction Model**: PASS. Leverages existing `/battle` hub slash commands and ephemeral interaction deferrals.
- **Principle V: Background Tasks**: PASS. `pvp_matchmaker_job` runs inside APScheduler event loop to trigger queue scans and backfill evaluations.
- **Principle VI: Error Handling**: PASS. Typed exceptions (`GhostSnapshotInvalidError`, `QueueBackfillError`) logged with full traceback and user-friendly Discord embeds.

## Project Structure

### Documentation (this feature)

```text
specs/054-instant-pvp-backfill/
├── plan.md              # Implementation Plan
├── research.md          # Phase 0 Research output
├── data-model.md        # Phase 1 Data Model output
├── quickstart.md        # Phase 1 Quickstart Validation Guide
├── contracts/           # Phase 1 Interface Contracts
│   ├── rpc_contracts.md # Supabase RPC function signatures & behavior
│   └── ui_contracts.md  # Discord embed & status UI contracts
└── checklists/
    └── requirements.md  # Specification Quality Checklist
```

### Source Code (repository root)

```text
supabase/
└── migrations/
    └── 103_instant_pvp_backfill.sql # Database tables, RPCs, and queue columns

packages/
└── pvp/
    └── pvp/
        ├── matchmaking.py  # Pure opponent selection, scoring & reward rules
        ├── models.py       # Pydantic models for GhostSnapshot & OpponentMode
        └── __init__.py

apps/
└── discord_bot/
    ├── cogs/
    │   └── battle_cog.py   # Discord `/battle` command handlers & view callbacks
    ├── core/
    │   ├── pvp_match.py    # Stadium runner with single-manager presentation support
    │   └── pvp_rpc.py      # Supabase RPC wrapper calls for backfill & snapshot refresh
    ├── embeds/
    │   └── pvp_embeds.py   # Queue stage embeds & mode badges (Live, Ghost, AI)
    └── tasks/
        └── pvp_matchmaker_job.py # Matchmaker background task handling backfill timing

tests/
├── test_pvp_ghost_backfill.py # Integration & unit tests for ghost matchmaking
└── test_pvp_matchmaking.py    # Standard PvP matchmaking tests
```

**Structure Decision**: Standard ElevenBoss Monorepo Layout (Pure packages under `packages/pvp`, bot UI under `apps/discord_bot`, database schema under `supabase/migrations`).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None* | Complies fully with all monorepo and database principles. | N/A |

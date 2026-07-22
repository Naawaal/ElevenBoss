# Implementation Plan: League Integrity (US-42.5)

**Branch**: `034-league-integrity` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/034-league-integrity/spec.md`

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: `032`, `033`, `026`, `027`

## Summary

Bind league integrity without forking the sporting calendar: **lifecycle transitions and prizes once**, **outage pauses without inventing forfeits**, **absence → assistant (not click-wins)**, **seats / leave-guild / AI prize bounds**. Close Critical gaps in pause metadata and status filters; harden acceptance tests around existing `_run_once` / economy keys.

**Technical approach**: (1) W0 audit → `contracts/league-integrity-audit.md`. (2) Unify pause paths to always set `pause_started_at` (+ correct open statuses); resume rebase remains `026` logic. (3) Confirm prize/promo idempotency (ledger keys + `promo_applied`); add guards/tests where thin. (4) Deadline vs Play already-played skip + paused Play copy fix. (5) Leave-guild = no delete (document + soft regression); AI prize = humans-only in `distribute_season_prizes` (grep/assert). (6) Optional thin migration **078** only if pause needs RPC/columns; prefer Python path fix first.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `league_lifecycle_engine`, `guild_resolver`, `league_operation_runs`, `distribute_season_prizes`, `apply_seasonal_promotion_relegation`, `026`/`027` rulebooks, US-42.3 seats, US-42.4 match runs

**Storage**: Existing `league_seasons` (`paused`, `pause_started_at`, `total_paused_seconds`), `league_operation_runs`, awards/history. Next migration number **078** if SQL needed.

**Testing**: Pytest/source guards for pause fields, prize keys, AI skip, already-played skip; optional smoke double catch-up

**Target Platform**: Discord bot (Render) + Supabase

**Project Type**: Monorepo integrity child (lifecycle/core patches; no new hubs)

**Performance Goals**: Catch-up O(overdue fixtures/transitions); pause/resume O(open matchdays)

**Constraints**: No second calendar; no Discord pause UI; single economy pipe; YAGNI — gap-fix overlay

**Scale/Scope**: Targeted Python fixes + tests; migration only if audit requires new columns/RPCs

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Lifecycle in core; Discord presents |
| II. DB via RPC | PASS | Prizes via `distribute_season_prizes` / economy pipe |
| III. Typing | PASS | Typed helpers |
| IV. Slash + defer | PASS | No new commands; `/league` only |
| V. APScheduler | PASS | Catch-up via existing lifecycle wake |
| VI. Friendly errors | PASS | Clear paused / already-played copy |
| VII. YAGNI | PASS | Overlay gaps only |

**Post-Phase 1 re-check**: PASS — contracts bind pause/prize/seat; no calendar rewrite.

## Project Structure

### Documentation (this feature)

```text
specs/034-league-integrity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── league-integrity-audit.md
│   ├── pause-resume.md
│   ├── transition-idempotency.md
│   ├── absence-vs-outage.md
│   └── seat-and-prize-bounds.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/discord_bot/core/guild_resolver.py          # pause + pause_started_at; status filter
apps/discord_bot/core/league_lifecycle_engine.py # pause_season statuses; resume; settle once
apps/discord_bot/cogs/battle_cog.py              # paused Play copy (no “admin resume”)
apps/discord_bot/cogs/league_cog.py              # unreachable / play gates if needed
apps/discord_bot/main.py                         # on_guild_remove already pauses

# Optional if audit requires:
supabase/migrations/078_league_integrity_guards.sql
scratch/apply_migration_078.py
scratch/smoke_league_integrity_078.py

tests/test_league_integrity_pause.py
tests/test_league_integrity_sql_guards.py  # if 078
# extend existing league lifecycle tests if present
```

**Structure Decision**: Prefer fixing pause call sites + acceptance greps over a mega “league integrity” RPC. Prize/promo idempotency already mostly in SQL — lock with tests; only patch if Critical hole remains.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Waves

| Wave | Scope | Exit |
|------|-------|------|
| **W0** | Freeze audit Critical/Soft/OK | Gaps agreed |
| **W1** MVP | Pause sets `pause_started_at`; correct status filters; Play blocked when paused with accurate copy | SC-002 class |
| **W2** | Transition/prize double-run tests; already-played deadline skip assert | SC-001/005 |
| **W3** | Seat/leave-guild/AI prize regression docs+tests | SC-004 / INV-12/15 |
| **W4** | Changelog if copy changes; Lock | Docs green |

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Decisions from codebase audit |
| [data-model.md](./data-model.md) | Season pause / operation / prize entities |
| [contracts/](./contracts/) | Pause, idempotency, absence, seats, audit |
| [quickstart.md](./quickstart.md) | Validate W0–W4 |

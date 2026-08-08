# Implementation Plan: Competitive Bot Match Experience (NSS v3)

**Branch**: `057-competitive-bot-match` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/057-competitive-bot-match/spec.md`

**Note**: Additive enhancement to `/battle bot` only. Feature flag defaults **OFF**. No PvP/matchmaking/queues/rivalries/new commands. Extends the **live NSS v2/v3 streaming** path actually used by Bot Battles (not a parallel competitive engine; not primarily the legacy Dixon-Coles/`MatchSimulationResult` loop).

## Summary

Add a flag-gated competitive match lifecycle after regulation: two five-minute extra-time periods, then a deterministic penalty shootout when still tied. Persist restart-safe phase/kick state on `match_runs`, extend stadium presentation with compact ET/pen banners and event-tier buffering, persist red-card Bot Battle suspensions via `player_suspensions` + atomic settlement, expand match stats/events (foul/FK/corner/offside), and optionally scale AI strength within bounded deltas. Phase-1 settlement keeps today’s XP/coin/fatigue/evolution pipes unchanged (no penalty-kick XP). Migration **109** seeds flags and schema; enablement is phased with the flag as kill switch.

## Technical Context

**Language/Version**: Python 3.11+ / CPython  
**Primary Dependencies**: Existing `packages/match_engine` (v2_simulator + v3), `discord.py`, Supabase async client, Pydantic  
**Storage**: PostgreSQL 15+ — extend `match_runs` / `match_events` / `match_history`; new `player_suspensions`; `game_config` flags  
**Testing**: `pytest` — engine phase/shootout/determinism; recovery; suspension RPC; economy regression with flag on/off  
**Target Platform**: Linux / Render Discord bot worker  
**Project Type**: Discord bot monorepo  
**Performance Goals**: Competitive matches remain within existing stadium update cadence; shootout prefers one edited message sequence; no material HTTP 429 spike vs baseline in soak  
**Constraints**: No `discord` in `packages/`; single XP/coin pipes (`process_match_result`, `apply_club_economy`); no new slash commands; flag default false; bot mid-match recovery must be newly durable (today bot runs abandon on interrupt)  
**Scale/Scope**: Extend NSS stream + battle stadium adapter + one shootout module + one suspension table/RPC; ~9 rollout phases; no Friendly/League scope in v1

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Monorepo**: PASS — Simulation/math in `packages/match_engine/`; Discord stadium/orchestration in `apps/discord_bot/` only.
- **Principle II — DB via RPC**: PASS — Suspensions create/decrement and any `decided_by` persistence via atomic settlement RPC extension; no per-player loops from `battle_cog`.
- **Principle III — Typing / Pydantic**: PASS — Serializable `MatchPhase`, `PenaltyShootoutState`, kick events as typed models.
- **Principle IV — Slash commands**: PASS — No new commands; `/battle bot` only.
- **Principle V — APScheduler**: N/A for core feature (no new periodic job required).
- **Principle VI — Error handling**: PASS — Discord send failures must not resimulate; recovery abandons only when state is unrestorable.
- **Principle VII — YAGNI**: PASS — Derived composure/reflexes (no new card attributes); no yellow accumulation; no parallel engine; flag off by default.

**Post-design re-check**: Still PASS — contracts keep Discord as adapter; shootout isolated; suspensions via RPC; NSS stream is the extension point.

## Project Structure

### Documentation (this feature)

```text
specs/057-competitive-bot-match/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── match-phase-lifecycle.md
│   ├── penalty-shootout.md
│   ├── suspensions-rpc.md
│   └── stadium-presentation.md
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

```text
packages/match_engine/
├── v2_simulator.py              # EXTEND: phase after FULL_TIME; ET intervals; event tiers
├── v3/                          # EXTEND: stream_match_v3 phase continuity + digests
├── penalty_shootout.py          # NEW: takers, ordering, kick resolve, sudden death
├── commentary_bank.json         # EXTEND: ET/pen templates
└── (legacy match_engine.py)     # optional parity later; NOT primary Bot Battle path

apps/discord_bot/
├── cogs/battle_cog.py           # orchestrate flag, phase banners, shootout UI, settlement inputs
├── core/match_runs.py           # persist phase / penalty_state / seeds
├── core/match_recovery.py       # bot mid-phase resume (new)
├── core/match_rewards.py        # pass decided_by; no pen XP
├── core/squad_validity.py       # block suspended cards
└── embeds/ / stadium handlers   # ET/pen presentation buffer

supabase/migrations/
└── 109_competitive_bot_match.sql

tests/
├── test_competitive_extra_time.py
├── test_penalty_shootout.py
├── test_competitive_recovery.py
├── test_player_suspensions.py
└── test_competitive_economy_regression.py
```

**Structure Decision**: Extend the live NSS streaming stack already used by `/battle bot`. Add one isolated `penalty_shootout.py`. Persist phase/kick state on existing match-run infrastructure. One forward migration for suspensions + flags + optional result columns.

## Complexity Tracking

> No Constitution Check violations.

| Concern | Mitigation |
|---------|------------|
| Spec brief assumed legacy interval engine | Research R1: implement on NSS v2/v3 stream; reuse legacy discipline metadata shapes where helpful |
| Bot recovery currently abandons | R2: durable phase + kick state + mid-stream event flush or snapshot before production ET/pens |
| Economy drift risk | R3: Phase 1 keeps existing reward policy; store `decided_by` for later calibration |

# Implementation Plan: Fix Match XP + Energy Regen

**Branch**: `001-fix-match-xp-energy` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fix-match-xp-energy/spec.md`

## Summary

Restore bot/league match development XP (friendlies unchanged) and ship the approved energy regen of 1 per 4 minutes (~6h 40m empty→full), with Discord status/error copy matching that rate.

**Technical approach**: Confirm/apply existing migrations `046` (regen) and `048` (`apply_card_xp` SECURITY DEFINER); harden schema verify for `prosecdef`; fix league recovery card hydration (`name` required by XP builder); align bot `REGEN_PER_MIN` / copy with `game_config`; ensure hard XP RPC failures surface to the manager (FR-004). No new slash commands or tables.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, supabase async ≥2.0, pydantic ≥2.0, player_engine / economy local packages

**Storage**: Supabase PostgreSQL — RPCs `process_match_result`, `apply_card_xp`, `sync_action_energy`; `game_config.energy_regen_per_min`

**Testing**: pytest (`tests/test_match_loop_hardening.py`, `tests/test_economy_flows.py`, extend as needed)

**Target Platform**: Discord bot (Render / long-running process) + hosted Supabase

**Project Type**: Monorepo — `apps/discord_bot` + `packages/*` + `supabase/migrations`

**Performance Goals**: Match reward path remains within Discord interaction followup window after defer; no new N+1 DB loops

**Constraints**: AGENTS.md — single XP pipe via `apply_card_xp`; no `discord` in `packages/`; no new hub commands; SDD reconcile into `.specify/specs/v1.0.0/` during implement; daily match XP cap 100/card remains

**Scale/Scope**: Bugfix + config/UI alignment; ~6–10 files; no new product surface

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Changes in `apps/discord_bot`, migrations, tests only |
| II. DB mutations via RPC / atomic paths | PASS | XP stays on `process_match_result` → `apply_card_xp`; energy via `sync_action_energy` / `game_config` |
| III. Typing / Pydantic at boundaries | PASS | No new cross-package models required; keep type hints on touched helpers |
| IV. Slash + defer | PASS | No new commands; existing deferred match flows |
| V. APScheduler | PASS | Energy is lazy `sync_action_energy`, not a new cron |
| VI. User-friendly errors | PASS | FR-004 requires surfacing hard XP failures (already re-raises; verify cog messaging) |
| VII. YAGNI | PASS | Reuse migrations 046/048; no new tables/commands |

**Post-Phase 1 re-check**: PASS — design adds no package-boundary or speculative surface area.

## Project Structure

### Documentation (this feature)

```text
specs/001-fix-match-xp-energy/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── match-xp-rpc.md
│   └── energy-regen-display.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
apps/discord_bot/
├── core/
│   ├── match_xp.py          # process_match_result payload + apply_match_xp_if_needed
│   ├── match_rewards.py     # bot → apply_match_xp_if_needed
│   ├── league_rewards.py    # league → apply_match_xp_if_needed
│   ├── economy_rpc.py       # REGEN_PER_MIN, format_action_energy_status
│   └── api_errors.py        # "every 6 minutes" copy
├── cogs/
│   └── battle_cog.py        # league recovery cards; match reward exception UX
supabase/
├── migrations/
│   ├── 046_progression_energy_rebalance.sql   # energy_regen_per_min = 0.25
│   └── 048_apply_card_xp_security_definer.sql # apply_card_xp SECURITY DEFINER
└── scripts/
    └── verify_required_schema.sql             # extend prosecdef check
packages/player_engine/player_engine/progression.py  # match_xp_reward (unchanged formulas)
packages/economy/economy/flows.py                    # defaults mirror (regen display if needed)
tests/
├── test_match_loop_hardening.py
└── test_economy_flows.py
change_log.md
.specify/specs/v1.0.0/spec.md   # reconcile US-25/US-35 regen + XP notes on implement
.specify/specs/v1.0.0/plan.md
```

**Structure Decision**: Existing ElevenBoss monorepo layout. No new packages or apps.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Approach (for `/speckit.tasks`)

1. **Ops / schema**: Verify remote `apply_card_xp.prosecdef = true` and `game_config.energy_regen_per_min = 0.25`; apply 048/046 if missing; extend `verify_required_schema.sql` (and latest migration guard if required by repo pattern) to assert DEFINER.
2. **Match XP**: Keep call sites; fix league recovery hydration so cards include `name` (and age fields used by `effective_card_age`) before `apply_match_xp_if_needed`; confirm bot/league hard failures reach manager-visible embeds (FR-004).
3. **Energy UI**: Set display regen to 1/4 min (prefer `get_game_config_numeric('energy_regen_per_min', 0.25)` on async paths; sync helpers default `1/4`); update `api_errors.py` + `change_log.md`.
4. **Tests**: Unit tests for regen minutes-to-full (0→100 ≈ 400 min); recovery payload / `build_process_match_result_rpc` with hydrated cards; no friendly XP regression.
5. **SDD**: Patch `.specify/specs/v1.0.0/spec.md` + `plan.md` regen lines (1/6 → 1/4) to match shipped behavior.

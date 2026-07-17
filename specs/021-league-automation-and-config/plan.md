# Implementation Plan: League Automation & Config

**Branch**: `021-league-automation-and-config` | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-league-automation-and-config/spec.md`

## Summary

Make guild seasonal leagues **self-running**: owners configure announce channel + mention role once in `/admin` (existing `guild_config` fields); a single **~00:05 UTC** APScheduler job owns registration open/close, Dynamics season start, daily tick (+ announce digest), season end, and Monday re-open after under-min failures — without admin Start/Open on the happy path.

**Technical approach**: Migration **`065_league_automation.sql`** — flags + registration-hour override + optional per-guild opt-in + season ownership marker. Refactor Dynamics start/tick helpers into callable services used by both legacy admin (when automation off) and `league_state_machine_job`. Consolidate `dynamics_daily_tick_job` into the state machine. Gate `/admin` League Management when automation on (Pause/Force End only).

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, existing `leagues` Dynamics helpers (020), `admin_cog` / `league_cog`

**Storage**: Supabase — `game_config` keys; optional `guild_config.league_automation_enabled`; `league_seasons.config_json` automation ownership + registration deadline; extend `verify_required_schema.sql`. **No new `guilds` table.**

**Testing**: pytest for registration eligibility / Monday reopen / admin gate helpers (pure); scratch smoke for job dry-run; Discord quickstart on pilot guild

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (discord_bot + migration; thin pure helpers in `packages/leagues` if needed)

**Performance Goals**: One 00:05 pass over automated guilds; per-guild work bounded (auto-sim already sequential); announce posts best-effort

**Constraints**: AGENTS.md / constitution — no `discord` in `packages/`; no new player slash; reuse 020 Dynamics; coins via existing MoMD/prize RPCs; grandfather in-flight seasons; YAGNI

**Scale/Scope**: 1 migration; state-machine job; admin gating + announce digests; extract shared start logic from `admin_cog`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Phase logic timers/pure rules in `packages/leagues` if needed; Discord posts in `apps/discord_bot/` |
| II. DB via RPC | PASS | Season mutations reuse existing start/prize/MoMD paths; no direct coin UPDATEs |
| III. Typing / Pydantic | PASS | Typed helpers / result models |
| IV. Slash + defer | PASS | Extend `/admin` + `/league` only |
| V. APScheduler | PASS | Single ~00:05 UTC orchestration (+ Monday branch for under-min reopen) |
| VI. Friendly errors | PASS | Missing channel shown in `/admin`; job logs skips |
| VII. YAGNI | PASS | Reuse guild_config; consolidate tick jobs; no new player commands |

**Post-Phase 1 re-check**: PASS — ownership via `config_json.automation`; per-guild flag optional on `guild_config`; no constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/021-league-automation-and-config/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── league-state-machine.md
│   ├── admin-automation-gates.md
│   ├── announce-digests.md
│   └── registration-windows.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/065_league_automation.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_065.py
scratch/smoke_league_automation.py

packages/leagues/leagues/automation.py          # NEW — eligibility: monday reopen, min humans, phase decisions (pure)
packages/leagues/leagues/__init__.py            # exports

apps/discord_bot/core/league_automation.py      # NEW — orchestrator: open_reg, close/start, tick+digest, conclude
apps/discord_bot/core/league_announce.py        # NEW or extend league_announcement.py — digest posts + role ping
apps/discord_bot/core/scheduler_jobs.py         # league_state_machine_job; retire/fold dynamics_daily_tick_job
apps/discord_bot/main.py                       # register single 00:05 job (replace/merge dynamics tick)
apps/discord_bot/cogs/admin_cog.py             # label channel/role; gate Open/Start when automation on;
                                              #   extract start_season_core(...) callable from admin_start_season
apps/discord_bot/cogs/league_cog.py             # hub copy if registration deadline from automation; auto_sim unchanged
apps/discord_bot/core/economy_rpc.py           # league_automation_enabled(db) (+ optional per-guild)

tests/test_league_automation_rules.py         # NEW — Monday reopen, min humans, ownership gates

change_log.md                                 # on implement ship
.specify/specs/v1.0.0/league-mode-design.md   # note autonomous ops on implement
```

**Structure Decision**: Orchestration in `apps/discord_bot/core/`; pure schedule rules in `packages/leagues`; extract shared season start from `admin_cog` rather than duplicating seating.

## Complexity Tracking

> No constitution violations requiring justification.

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research + decisions | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Frozen implementation decisions (from research)

| ID | Decision |
|----|----------|
| **D1** | Global flag `league_automation_enabled` default **false**. Optional per-guild `guild_config.league_automation_enabled` (NULL = inherit global). Effective on iff global && (guild NULL or true). |
| **D2** | Reuse `guild_config.league_channel_id` + `announcement_role_id`. Clarify `/admin` labels to “League announce channel” / “League mention role”. No `guilds` table. |
| **D3** | Autonomous seasons always Dynamics (`pacing_mode='dynamics'`); require `league_dynamics_enabled` **or** treat automation as implying Dynamics for owned seasons (prefer: automation effective implies Dynamics start path even if dynamics flag off — **OR** require both flags. **Frozen:** automation start path **forces Dynamics** seating/windows; reading `league_dynamics_enabled` not required when automation owns the season). |
| **D4** | Season ownership: `config_json.automation = true` (+ `registration_closes_at` ISO) set when job opens registration / starts season. Manual seasons omit marker. Job only mutates owned seasons + opens new ones when eligible. |
| **D5** | Single job `league_state_machine_job` cron **00:05 UTC**. Absorbs Dynamics tick for automated guilds’ active Dynamics seasons. Keep `dynamics_daily_tick_job` **only** for `pacing_mode=dynamics` seasons **without** automation ownership **OR** fold all Dynamics ticks into state machine always (simpler): **Frozen — fold**: state machine runs Dynamics tick for all `pacing_mode='dynamics'` active seasons; remove separate `dynamics_daily_tick_job` registration to avoid double-sim. |
| **D6** | Tick order per guild: auto_sim_expired → update_current_matchday (MoMD) → announce digest if automation effective + channel set. |
| **D7** | Registration: 48h via `league_automation_registration_hours` (default 48; distinct from legacy `league_registration_hours` 72). Min humans = `league_min_humans` (default 2). |
| **D8** | Under-min close: delete/complete registration season as failed; set `guild_config.next_auto_registration_at` = next Monday 00:05 UTC; announce shortfall. Job opens registration only if `now >= next_auto_registration_at` (or NULL) and no active/registration season. |
| **D9** | After successful season complete (automation-owned): open next registration **same job run** if channel ok (SC-003). |
| **D10** | `/admin` when automation effective: hide/disable Open Registration + Start Season; keep Pause + Force End. |
| **D11** | Extract `start_dynamics_season_from_registration(...)` shared by admin (flag off) and automation job — seating/fixtures/threads from 020 path. |
| **D12** | Migration **065**; verify guards; scratch apply + smoke. |
| **D13** | Idempotency: open-reg only if none; start only if registration past close; digest keyed by `(season_id, matchday)` optional table or skip if already posted (`config_json.last_digest_matchday`). |
| **D14** | Announce post failures never roll back season transitions. |

## Next command

`/speckit.implement` — start at T001 (see [tasks.md](./tasks.md)).

**Tasks**: [tasks.md](./tasks.md) (T001–T030)

**Note**: Depends on 020 League Dynamics being shipped/available. Do not merge with transfer/wage scopes.

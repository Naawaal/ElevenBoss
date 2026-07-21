# Implementation Plan: League Rulebook and Autonomous Lifecycle Engine V1

**Branch**: `026-league-lifecycle-rulebook` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-league-lifecycle-rulebook/spec.md` (clarifications Q1=A, Q2=A, Q3=C resolved)

## Summary

Freeze and implement a **single authoritative Guild Seasonal League rulebook**: 21-day cycle (48h registration → 24h preparation → 14 daily matchdays → 24h settlement → 72h offseason), 8-club double round-robin, guild-frozen IANA timezone + local resolution hour with precomputed UTC windows, assistant-manager lineup repair before forfeit, 0–0 double-forfeit (0 points), human-first promotion/relegation, and exactly-once recoverable lifecycle transitions.

**Technical approach**: New migration **`070_league_lifecycle_v1.sql`** expands season/matchday/fixture lifecycle states, freezes `ruleset_version` / `engine_version` / schedule snapshot on seasons, adds operation journal + outbox for idempotency and Discord-decoupled presentation. Pure rulebook math lives in `packages/leagues` (schedule, seating, standings, forfeit, assistant repair inputs). App-layer **`LeagueLifecycleEngine`** in `apps/discord_bot/core/` is the only place that advances competitive state; APScheduler becomes a **thin wake-up** (≈ every 5 minutes + startup recovery). Feature-flagged **per-guild exclusive cutover** grandfathers living 020/021 seasons; after cutover, new seasons use V1 only — no permanent dual modes. No new player slash commands; `/admin` + `/league` reuse shared transitions.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, stdlib `zoneinfo` (IANA TZ / DST), existing `packages/leagues`, `match_engine` fixture generator, `apply_club_economy`, match run / lock RPCs

**Storage**: Supabase — alter `guild_config`, `league_seasons`, `league_fixtures` (+ related); new tables for matchdays, final standings, transition journal, operation runs, outbox (see [data-model.md](./data-model.md)); RLS + `verify_required_schema.sql`; RPCs for atomic settle/rewards where money moves

**Testing**: pytest for zoneinfo window generation (DST gap/overlap), double-forfeit standings math, assistant lineup priority, promo/releg human-first, exactly-once operation keys (100× replay), pause/resume rebase; scratch smoke for migration + engine catch-up

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (`packages/leagues` + `apps/discord_bot` + `supabase/migrations`)

**Performance Goals**: One wake-up processes all due transitions for active V1 seasons within the 5-minute tick budget for typical guild counts; fixture settlement remains single-fixture leased; catch-up after multi-hour outage completes without duplicate settlements (SC-003, SC-004)

**Constraints**: AGENTS.md / constitution — no `discord` in `packages/`; coins only via `apply_club_economy`; schema only via **070+**; defer interactions; **no new player slash commands**; weekly Division Rank stays decoupled; Ponytail — one lifecycle engine, thin scheduler, admin uses same transitions; do **not** implement scheduler business rules before pure rulebook helpers exist

**Scale/Scope**: One major migration; lifecycle engine + recovery; rewire 021 state machine into wake-up adapter; `/admin` timezone/hour + cutover flag; hub deadline copy; grandfather 020/021 until completion

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Schedule/forfeit/standings/assistant pure logic in `packages/leagues`; Discord/outbox publish in `apps/discord_bot/` |
| II. DB via RPC | PASS | Deposits, prizes, MoMD (if retained), promo persist via RPCs / `apply_club_economy`; fixture settle via leased ops + unique keys |
| III. Typing / Pydantic | PASS | Pydantic models at package boundaries (windows, settle results, transition outcomes) |
| IV. Slash + defer | PASS | Extend `/league hub` + `/admin` only |
| V. APScheduler | PASS | Frequent wake-up only; no competitive rules in job body |
| VI. Friendly errors | PASS | Map illegal XI / closed window / paused / cutover messages to embeds |
| VII. YAGNI | PASS | No playoffs; no dual selectable modes; no new slash commands; bots support structure only |

**Post-Phase 1 re-check**: PASS — entities map to migration 070; contracts freeze transitions without dual engines; grandfather via `ruleset_version` / cutover flag; no constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/026-league-lifecycle-rulebook/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── lifecycle-transitions.md
│   ├── matchday-schedule.md
│   ├── fixture-resolution.md
│   ├── promotion-relegation.md
│   ├── cutover-and-rollback.md
│   └── admin-and-hub-surfaces.md
├── checklists/requirements.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/070_league_lifecycle_v1.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_070.py
scratch/smoke_league_lifecycle_v1.py

packages/leagues/leagues/lifecycle_states.py      # status enums / allowed transitions
packages/leagues/leagues/schedule.py              # IANA TZ + local hour → UTC windows (DST rules)
packages/leagues/leagues/assistant_lineup.py      # repair priority inputs → lineup plan
packages/leagues/leagues/forfeit_rules.py         # 3-0 / double_forfeit standings deltas
packages/leagues/leagues/seasonal_divisions.py    # extend: human-first promo, reduce-movement
packages/leagues/leagues/standings.py             # double_forfeit aware aggregation
packages/leagues/leagues/operation_keys.py        # idempotency key builders
packages/leagues/leagues/__init__.py

apps/discord_bot/core/league_lifecycle_engine.py  # LeagueLifecycleEngine.process_due_transitions
apps/discord_bot/core/league_recovery.py          # stalled ops, startup catch-up
apps/discord_bot/core/league_outbox.py             # publish pending Discord events
apps/discord_bot/core/league_automation.py        # thin wake-up adapter over engine (021 fold-in)
apps/discord_bot/core/scheduler_jobs.py           # register ~5min wake-up + startup recovery
apps/discord_bot/core/league_journal.py           # presentation only (consume outbox)
apps/discord_bot/core/league_announce.py          # presentation only
apps/discord_bot/cogs/admin_cog.py                # TZ/hour config, cutover, shared transitions
apps/discord_bot/cogs/league_cog.py                # hub deadlines from frozen windows
apps/discord_bot/cogs/battle_cog.py                # early presentation; settle via engine path
apps/discord_bot/main.py                          # job registration

tests/test_league_schedule_windows.py
tests/test_double_forfeit_standings.py
tests/test_assistant_lineup_priority.py
tests/test_lifecycle_idempotency.py
tests/test_pause_resume_rebase.py
tests/test_cutover_grandfathering.py

change_log.md                                     # on ship
.specify/specs/v1.0.0/league-mode-design.md       # reconcile: V1 rulebook supersedes for cutover guilds
```

**Structure Decision**: Extend existing monorepo surfaces. Competitive rules in `packages/leagues`; orchestration + Discord IO in `apps/discord_bot/core/league_lifecycle_engine.py`. Do not add a new app or package.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| New lifecycle tables (matchdays, journal, ops, outbox) beyond 020/021 columns | Spec requires auditable exactly-once transitions, immutable finals, Discord-decoupled progression | Stuffing everything into `config_json` cannot guarantee unique ops, final standings immutability, or outbox retry |
| Broader season status enum | Spec forbids labeling cancel/fail as `completed` | Reusing only `registration/active/paused/completed` collapses failure modes and breaks SC/audit |

## Implementation Sequence (normative)

1. Approve this plan → `/speckit.tasks`
2. Migration 070 + pure rulebook helpers + tests (schedule, forfeit, seating)
3. `LeagueLifecycleEngine` + operation keys + recovery (no Discord required for competitive settle)
4. Outbox → announce/journal presentation
5. Thin scheduler wake-up; fold 021 job
6. Admin TZ/hour + cutover; hub copy
7. Pilot guild cutover; grandfather living seasons
8. Update `change_log.md` + SDD reconcile on ship

Do **not** invent competitive rules inside the scheduler while coding.

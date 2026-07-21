# Implementation Plan: Autonomous League Administration Policy

**Branch**: `027-league-autonomous-admin` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-league-autonomous-admin/spec.md`

## Summary

Make the Guild Seasonal League a **fully autonomous internal system** on Discord: guild admins may configure **only League Time** (IANA timezone + local daily resolution hour) under `/admin → Server Settings → League Time`. Remove `/admin → League Management` lifecycle and competitive controls. League Time changes apply to **future seasons only**; active seasons keep their frozen timing snapshot. Unconfigured guilds default to **`UTC` + `00:00`** without blocking progression. Competitive transitions remain owned by `LeagueLifecycleEngine` (from `026`); this feature strips Discord authority, enforces non-blocking defaults, and adds **operator-only** recovery that reuses the same engine (idempotent, audited) — never ordinary Discord admin “break glass” tools.

**Technical approach**: Mostly Discord surface + engine policy changes on top of migration `070` schema (reuse `guild_config.league_timezone` / `league_resolution_hour_local` and season freeze columns). Optional small forward migration `072` only if `game_config` default hour / verify guards need alignment. Pure IANA validation helpers stay in `packages/leagues` (or thin reuse of existing `zoneinfo` paths). Operator recovery lands as a trusted CLI/script + wake-job stalled-op recovery — not a Discord menu.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, stdlib `zoneinfo`, existing `LeagueLifecycleEngine` / outbox / recovery from `026`

**Storage**: Reuse `guild_config` League Time columns + `league_seasons` frozen timezone/hour/`ruleset_snapshot`/`phase_deadlines`/`league_matchdays.window_*` from `070`. No new competitive tables required for the Discord policy. Optional `072` for `game_config` default resolution hour → `0` and schema-guard extensions if needed.

**Testing**: pytest for IANA reject (offsets), default coalesce UTC/0, “guild setting change does not rewrite active season windows”, admin surface inventory (no lifecycle custom_ids), recovery CLI / wake idempotency replay; inventory assert against forbidden Discord controls

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase; operator CLI run from trusted host with `DATABASE_URL` / service credentials

**Project Type**: Monorepo feature (`apps/discord_bot` UI + core policy, `packages/leagues` validation helpers, optional `supabase/migrations/072_*`, `scripts/` or `scratch/` operator recover)

**Performance Goals**: League Time save is a single guild_config upsert; recovery wake continues to process due transitions within the existing ~5-minute tick budget

**Constraints**: Constitution / AGENTS.md — no `discord` in `packages/`; no Discord interaction mutates lifecycle phase; scheduler remains thin wake-up; no new player slash commands; coins/standings/promo only via existing engine/RPC paths; Ponytail — delete League Management controls rather than hide behind flags; amend `026` admin contract so docs do not reintroduce Discord pause/force-end

**Scale/Scope**: One admin hub restructure; engine default/coalesce + prepare no longer hard-fails on NULL TZ; remove admin lifecycle handlers from Discord; operator recover script; reconcile `026` admin-and-hub contract + change_log on ship

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | IANA/preview helpers pure in `packages/leagues` if needed; Discord views only in `apps/discord_bot` |
| II. DB via RPC | PASS | League Time is guild preference upsert (no multi-row financial loop); competitive mutations stay in existing engine/RPC paths; recovery never direct-updates standings/coins |
| III. Typing / Pydantic | PASS | League Time input + preview models at package boundary |
| IV. Slash + defer | PASS | Extend `/admin` only; defer before DB; no new player slash commands |
| V. APScheduler | PASS | Wake remains thin; stalled recovery may be added to wake without embedding competitive rules |
| VI. Friendly errors | PASS | Invalid TZ/offset → clear ephemeral embed |
| VII. YAGNI | PASS | No operator web portal; no Discord break-glass menu; no new competitive tables unless proven necessary |

**Post-Phase 1 re-check**: PASS — data model reuses `070` entities; contracts freeze Discord surface to League Time + Announcements (presentation); operator recovery is script/wake-only; no constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/027-league-autonomous-admin/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── discord-admin-surfaces.md
│   ├── league-time-settings.md
│   └── operator-recovery.md
├── checklists/requirements.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
# Optional forward migration (only if game_config / verify need it)
supabase/migrations/072_league_time_defaults.sql
supabase/scripts/verify_required_schema.sql

packages/leagues/leagues/league_time.py          # IANA validate, reject offsets, preview/coalesce defaults
packages/leagues/leagues/__init__.py

apps/discord_bot/cogs/admin_cog.py               # Server Settings → League Time; strip League Management lifecycle
apps/discord_bot/core/league_lifecycle_engine.py # coalesce UTC/00:00 on prepare; never require Discord config
apps/discord_bot/core/league_recovery.py         # stalled ops on wake; alert/log on retry exhaustion
apps/discord_bot/core/scheduler_jobs.py          # wake calls stalled recovery + due transitions + outbox
apps/discord_bot/main.py                         # unchanged job cadence unless wiring tweak

scripts/league_lifecycle_recover.py              # operator-only: wake engine + stalled recover + outbox (audited)
# or scratch/ if kept experimental — prefer scripts/ for documented ops

tests/test_league_time_validation.py
tests/test_league_time_defaults_freeze.py
tests/test_admin_surface_inventory.py           # forbidden custom_ids / handlers absent

specs/026-league-lifecycle-rulebook/contracts/admin-and-hub-surfaces.md  # amend: Discord lifecycle controls removed
change_log.md                                    # on ship
```

**Structure Decision**: Extend existing monorepo. Do not add a new package or Discord cog. Competitive rulebook stays in `026` / `LeagueLifecycleEngine`; this feature owns Discord authority removal, League Time UX, default coalesce, and operator recovery entry points.

## Complexity Tracking

> No constitution violations requiring justification.

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|------------|--------------------------------------|
| Operator CLI (scripts/) | Spec requires non-Discord recovery after removing Discord break-glass | Relying only on 5-min wake leaves no trusted manual retry when alerts fire |
| Amend 026 admin contract | Prevents plan/implement drift reintroducing Discord pause/force-end | Leaving 026 docs unchanged would contradict shipping 027 |

## Implementation Sequence (normative)

1. Freeze research decisions (defaults UTC/00:00, strip Discord lifecycle, Announcements stay, cutover not Discord-tunable)
2. Pure `league_time` validation + coalesce helpers + tests
3. Engine prepare uses coalesce; active-season freeze unchanged by guild_config updates
4. Restructure `/admin`: Server Settings → League Time; delete League Management lifecycle buttons/handlers
5. Wake-job stalled recovery + operator `scripts/league_lifecycle_recover.py`
6. Amend `026` admin contract + inventory tests + change_log
7. Quickstart validation on a pilot guild

# Implementation Plan: League Dynamics Overhaul

**Branch**: `020-league-dynamics` | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-league-dynamics/spec.md`

## Summary

Replace rolling ~48h guild-league windows with a **flagged Daily Tick** (hard close **00:00 UTC**, auto-sim + settlement ~**00:05 UTC**), default seasons to **14 days / 8-club double RR**, add a **seasonal division pyramid** (exactly 8 clubs per tier, split when humans > 8, top/bottom 2 promo-releg), and award **Manager of the Matchday** (manual human wins only, 2,000 coins, Journal) — without new slash commands and without merging into the weekly Division Rank ladder.

**Technical approach**: Migration **`064_league_dynamics.sql`** — `game_config` flag + tunables; `league_seasons.pacing_mode`; `league_participants.division_tier`; `league_fixtures.resolved_by`; `league_members.seasonal_division_tier`; MoMD award table + RPC `award_manager_of_the_matchday`; season-end `apply_seasonal_promotion_relegation`; extend `distribute_season_prizes` for per-tier payouts. Pure helpers in `packages/leagues`. Rewire `admin_start_season` windows + division seating; cron tick beside `daily_recovery_job`; keep 10-min interval for **legacy** seasons only.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, existing `leagues` + `match_engine` fixture gen + `apply_club_economy`

**Storage**: Supabase — alter `league_seasons`, `league_participants`, `league_fixtures`, `league_members`; new MoMD award table; `game_config` keys; RLS on new table; extend `verify_required_schema.sql`

**Testing**: pytest for UTC window math, fixed-2 promo/releg, MoMD selection/eligibility; RPC/smoke via scratch; Discord quickstart for flag off/on + Journal copy

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (packages + discord_bot + migrations)

**Performance Goals**: Daily tick finishes all expired fixtures for active Dynamics seasons within ~15 minutes (SC-001); MoMD selection is one set-based query per settled matchday

**Constraints**: AGENTS.md / constitution — no `discord` in `packages/`; coins only via `apply_club_economy`; columns/RPCs only in **064+**; defer interactions; **no new slash commands**; keep weekly Division Rank decoupled; YAGNI / Ponytail (modify existing hub, admin, scheduler, Journal)

**Scale/Scope**: 1 migration; leagues package helpers; admin start + league hub copy + scheduler; flag default **false**; grandfather `pacing_mode='legacy'` for in-flight seasons

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Window/promo/MoMD pure math in `packages/leagues`; Discord only in `apps/discord_bot/` |
| II. DB via RPC | PASS | MoMD payout + promo persist + prize path via RPCs / `apply_club_economy`; no direct `players.coins` updates |
| III. Typing / Pydantic | PASS | Typed helpers + result models at package boundary |
| IV. Slash + defer | PASS | Extend `/league hub` + admin season lifecycle only |
| V. APScheduler | PASS | Cron 00:05 UTC Dynamics tick; legacy keeps interval job |
| VI. Friendly errors | PASS | Map auto-sim / closed-window / flag messages to embeds |
| VII. YAGNI | PASS | No Winners Cup; no merge with weekly ladder; no new awards hub |

**Post-Phase 1 re-check**: PASS — one season row multi-tier; `resolved_by` for MoMD eligibility; grandfather via `pacing_mode`; no constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/020-league-dynamics/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── daily-tick-windows.md
│   ├── division-seating-promo.md
│   ├── manager-of-the-matchday.md
│   └── league-hub-copy.md
└── tasks.md                # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/064_league_dynamics.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_064.py
scratch/smoke_league_dynamics.py          # optional

packages/leagues/leagues/dynamics_windows.py   # NEW — UTC midnight window assignment
packages/leagues/leagues/seasonal_divisions.py  # NEW — seat humans, fixed-2 promo/releg
packages/leagues/leagues/momd.py               # NEW — eligible win rank / pick winner
packages/leagues/leagues/__init__.py           # exports
# keep calculator.compute_promotions_relegations for WEEKLY ladder only

apps/discord_bot/cogs/admin_cog.py             # Dynamics start: 14d default, 8/tier seating, UTC windows
apps/discord_bot/cogs/league_cog.py             # hub copy; standings by tier; matchday settlement → MoMD
apps/discord_bot/cogs/battle_cog.py             # set resolved_by='manual' on human play path
apps/discord_bot/core/scheduler_jobs.py         # dynamics_daily_tick_job; legacy interval filter
apps/discord_bot/main.py                       # cron 00:05 UTC tick (beside daily_recovery)
apps/discord_bot/core/league_journal.py         # MoMD Journal line; optional per-tier standings
apps/discord_bot/core/league_announcement.py    # midnight UTC / 14-day / division copy
apps/discord_bot/core/api_errors.py            # map new RPC errors if needed

tests/test_league_dynamics_windows.py          # NEW
tests/test_seasonal_promo_relegation.py        # NEW
tests/test_momd_selection.py                   # NEW

change_log.md                                  # on implement ship
.specify/specs/v1.0.0/league-mode-design.md    # reconcile pacing on implement
```

**Structure Decision**: Extend existing leagues package + league/admin/scheduler surfaces; do not add apps/packages.

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
| **D1** | Flag `league_dynamics_enabled` default **false**. Per-guild optional override later via `guild_config` only if needed; v1 = global flag + season `pacing_mode`. |
| **D2** | `league_seasons.pacing_mode` ∈ `legacy` \| `dynamics`. Set at **season start** from flag. Never mutate mid-season. In-flight seasons without column → backfill **`legacy`**. |
| **D3** | Dynamics defaults: `duration_days=14`, `max_clubs` effective **8 per tier**, double RR → `total_matchdays=14`. Admin modal default when flag on: **14** (legacy seasons untouched). |
| **D4** | Window math (Dynamics): for matchday `N`, `window_end = date_trunc('day', start_time AT TIME ZONE 'UTC') + N * interval '1 day'` (UTC midnight). `window_start` = previous end (or `start_time` for N=1). All fixtures on matchday N share the same end. |
| **D5** | Scheduler: **cron 00:05 UTC** `dynamics_daily_tick_job` only processes `pacing_mode='dynamics'` active seasons. Keep **10-min interval** job for **`legacy` only**. Hub-open opportunistic auto-sim remains for both. |
| **D6** | Multi-tier = **one** `league_seasons` row; `league_participants.division_tier` (1=top); fixtures only within same tier; synced matchday index across tiers. |
| **D7** | Seating: humans sorted by `league_members.seasonal_division_tier` (asc), then prior finish rank if available, else registration order. Fill tier 1 with up to 8 humans, overflow to tier 2, … Bot-fill each tier to exactly 8. |
| **D8** | Promo/releg: pure helper fixed **top 2 / bottom 2** between adjacent human standings (AI excluded from swap lists). Persist onto `league_members.seasonal_division_tier` at season complete. Skip / shrink when human N &lt; 4 in a tier. |
| **D9** | `league_fixtures.resolved_by` ∈ `manual` \| `auto_sim` \| NULL (unplayed). Human play path → `manual`; auto-sim / null `active_player_id` path → `auto_sim`. |
| **D10** | MoMD: **one** winner per `(season_id, matchday)` across all tiers. Eligible = human winner, `resolved_by='manual'`, opponent any. Rank by margin DESC, GF DESC, club_id ASC. Coins default **2000** via `apply_club_economy`. No eligible → no award. |
| **D11** | MoMD idempotency: table `league_matchday_manager_awards` UNIQUE `(season_id, matchday)` + ledger key `momd:{season_id}:{matchday}`. |
| **D12** | Season prizes: extend `distribute_season_prizes` to pay **per division_tier** (humans only table within tier). Promo/releg after prizes. |
| **D13** | Weekly Division Rank (`players.division`, Monday 20%) **unchanged**; UI labels disambiguate (“Division 1” seasonal vs “Weekly Rank”). |
| **D14** | Migration **064**; extend verify + RLS on MoMD table; scratch apply script. |
| **D15** | Custom admin duration under Dynamics: if flag on and admin sets ≠14, still assign midnight windows as `duration_days / 14` is rejected — **constrain**: Dynamics seasons force `duration_days=14` and 8/tier (document in admin embed). Legacy path keeps full modal flexibility. |

## Next command

Ready to ship behind flag. Enable with:

```sql
UPDATE game_config SET value_json = 'true'::jsonb WHERE key = 'league_dynamics_enabled';
```

**Tasks**: [tasks.md](./tasks.md) (T001–T042 complete)

**Note**: Do not merge scope with 017/018/019 workstreams.

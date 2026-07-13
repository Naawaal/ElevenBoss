# Implementation Plan: Youth Academy Integration & Functional Workflow

**Branch**: `015-youth-academy` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-youth-academy/spec.md`

## Summary

Turn the Youth Academy from “upgrade + Monday dump onto roster” into a managed holding phase: seat new intake/scout prospects in academy slots, grow them passively by academy level, promote into senior club or release to free slots. Keep weekly free intake; add paid timed scouting as a coin sink. UI entry is **`/profile` → Manage Academy`** (no new slash command). Grandfather existing senior intake cards.

**Technical approach**: Flag academy seats on `player_cards` (`in_academy`), extend `process_youth_intake` for slot-capped seating, add growth/promote/release/scout RPCs + pure math in `packages/`, deepen `store_facilities` views, schedule daily academy growth next to `process_daily_recovery`. Coins only via `apply_club_economy`. Academy growth does **not** use `apply_card_xp` (auto-stat OVR ticks until promote).

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, APScheduler, pydantic, existing `player_engine` / `economy` / `gacha`

**Storage**: Supabase — extend `player_cards` + `players`; new `scouting_reports`; `game_config` keys; migration `060_youth_academy_workflow.sql`

**Testing**: pytest for pure math (`youth_math`, slot caps, scout cost tiers, star bands); RPC smoke via scratch apply + verify schema

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (packages + discord_bot + migrations)

**Performance Goals**: Daily growth job processes all academy cards in one RPC (set-based); intake remains per-manager loop but slot logic inside RPC; scout dispatch &lt; Discord defer window

**Constraints**: AGENTS.md — no `discord` in `packages/`; no XP/coin bypasses; columns/RPCs only via migrations; no new slash command; RLS on new tables; verify schema before bot ship; `change_log.md` + reconcile `.specify/specs/v1.0.0/` on implement; YAGNI — no U18 league

**Scale/Scope**: ~1 migration; ~3–5 pure modules/helpers; facilities UI extension; 2 scheduler hooks (daily growth + age-out); hybrid scouting P2 in same release behind P1 seating/grow/promote

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Math/generation in `packages/`; views/tasks in `apps/discord_bot/` |
| II. DB via RPC | PASS | Intake/promote/release/scout/growth via atomic RPCs; coins via `apply_club_economy` |
| III. Typing / Pydantic | PASS | Typed helpers + models at package boundaries |
| IV. Slash + defer | PASS | No new slash; hub buttons defer immediately |
| V. APScheduler | PASS | Daily growth job; reuse Monday intake job |
| VI. Friendly errors | PASS | Map RPC exceptions to ephemeral embeds |
| VII. YAGNI | PASS | Flag on `player_cards` not parallel player system; no U18 sim |

**Post-Phase 1 re-check**: PASS — contracts keep academy growth off `apply_card_xp`; Manage Academy is hub extension authorized by FR-016; senior cap introduced as soft `game_config` because none exists today.

## Project Structure

### Documentation (this feature)

```text
specs/015-youth-academy/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── academy-growth-math.md
│   ├── process-youth-intake-seating.md
│   ├── promote-release-academy.md
│   ├── scouting-dispatch-claim.md
│   └── manage-academy-ui.md
└── tasks.md                 # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
supabase/migrations/060_youth_academy_workflow.sql
supabase/scripts/verify_required_schema.sql          # extend guards
scratch/apply_migration_060.py

packages/economy/economy/facility_effects.py         # academy_slot_cap(); scout tier costs/durations
packages/economy/economy/flows.py                    # optional scout cost mirrors if needed
packages/player_engine/player_engine/youth_math.py   # NEW — growth, ready flag, star band, age-out
packages/player_engine/player_engine/youth_intake.py # seat payload flag / reuse tiers
packages/player_engine/player_engine/__init__.py      # exports
packages/gacha/gacha/…                               # optional scout batch wrapper reusing generate_youth_intake

apps/discord_bot/cogs/profile_cog.py                 # Manage Academy button
apps/discord_bot/views/store_facilities.py           # YA upgrade copy (slots/growth; no Manage button)
apps/discord_bot/views/academy_hub.py                # NEW — list / promote / release / scout
apps/discord_bot/embeds/academy_embeds.py            # NEW
apps/discord_bot/embeds/youth_intake_embeds.py       # academy seating copy
apps/discord_bot/tasks/youth_intake_notifier.py      # unchanged generate; RPC seats with flag
apps/discord_bot/tasks/academy_growth_job.py         # NEW — call process_daily_academy_growth
apps/discord_bot/core/scheduler_jobs.py              # wire daily job
apps/discord_bot/main.py                             # register cron (e.g. 00:10 UTC after recovery)
apps/discord_bot/cogs/squad_cog.py                   # reject in_academy on assign
apps/discord_bot/cogs/marketplace_cog.py             # exclude in_academy from sell list
apps/discord_bot/cogs/development_cog.py            # exclude in_academy from drill/fusion targets

tests/test_youth_math.py                             # NEW
tests/test_academy_slots.py                          # NEW (slot caps + ready threshold)

change_log.md
.specify/specs/v1.0.0/spec.md                        # US-32/33 amend on implement
```

**Structure Decision**: Reuse `player_cards` with `in_academy` holding flag (ponytail) rather than a parallel `youth_prospects` table. Manage Academy lives under `/profile`; Club Facilities keeps YA/TG upgrades. Pure formulas live in `player_engine`/`economy`; mutations only in migration RPCs.

## Complexity Tracking

> No constitution violations requiring justification.

| Topic | Choice | Simpler alternative rejected because |
|-------|--------|--------------------------------------|
| Separate `youth_prospects` table | Rejected | Duplicates card model; breaks profile/age/factory reuse |
| New `/academy` slash | Rejected (FR-016) | Spec + hub convention |
| Academy via `apply_card_xp` | Rejected | Would grant SP and fight “auto-allocate to POT” design |
| Hard-migrate old intake to academy | Rejected (FR-017) | Squad breakage risk |

## Implementation Notes (for `/speckit.tasks`)

1. **Migration 060 first** — columns, RLS, RPCs, schema guard; apply + verify before bot wiring.
2. **P1 path**: seating intake → Manage Academy list → growth job → promote/release → squad/marketplace/dev exclusions.
3. **P2 path**: scout dispatch/claim UI + DM optional; same academy seat insert path.
4. **Grandfather**: `in_academy DEFAULT FALSE`; only new inserts from academy RPCs set `TRUE`.
5. **Senior cap**: `game_config.senior_roster_cap` default `48`; promote counts non-academy non-retired cards.
6. **Growth**: set-based daily RPC; mirror formula in `youth_math.py`.
7. **Age-out**: age ≥ 20 (after DOB/season age) → try promote else delete + notify; run inside daily growth RPC or immediately after.
8. **Wiring check**: every RPC must have call site (intake job, academy hub buttons, daily cron).
9. **Cleanup**: update facilities/intake copy that says prospects “join your roster”; grep `process_youth_intake` callers.

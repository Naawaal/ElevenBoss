# Implementation Plan: Shelve PvP and Fix Surviving Automations

**Branch**: `056-shelve-pvp-automation` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/056-shelve-pvp-automation/spec.md`

**Note**: Cleanup + targeted fix only. No new product surface. End state = pre-PvP ElevenBoss + version-gated changelog + Top.gg vote reminder.

## Summary

Selectively erase the shelved PvP initiative (matchmaking, rivalries, queue, Practice/ghost fallback, flags, migrations 098–106, specs/tests/scratch) while preserving Youth Academy (095–097) and Feature 055 automations (migration 107). Restore `/battle` to Bot Battle + Friendly using the last pre-PvP battle baseline (`1737df6`) for mode UX, without discarding later non-PvP match-integrity fixes. Fix changelog dedupe so posting keys on **version header only** (not `version:commit`). Tighten vote-reminder window dedupe, cooldown scheduling, and DM→Store fallback so each vote window yields at most one notice. Ship one forward migration (`108`) to drop applied PvP schema and redefine changelog claim RPCs for version-only keys.

## Technical Context

**Language/Version**: Python 3.11+ / CPython  
**Primary Dependencies**: `discord.py >= 2.7.0`, `supabase` async client, `apscheduler`, `pydantic >= 2.0.0`  
**Storage**: PostgreSQL 15+ (Supabase); `game_config`, `topgg_vote_reminders`; forward migration drops PvP objects  
**Testing**: `pytest` at repo `tests/` (changelog version-key tests; vote-reminder tightening; no new PvP tests)  
**Target Platform**: Linux / Render Discord bot worker  
**Project Type**: Discord bot monorepo (`apps/discord_bot/` + `packages/` + `supabase/`)  
**Performance Goals**: Startup changelog check &lt; 2s and silent on same version; reminder batch still bounded (≤100 rows / 30 min job)  
**Constraints**: Monorepo rules (no `discord` in `packages/`); no coin/XP pipe changes; no wholesale revert of mixed Academy+PvP commit; never rewrite applied migrations in place; zero remaining active PvP product hits after grep gate  
**Scale/Scope**: Delete ~1 package + ~6 bot modules + migrations 098–106 + specs 053/054 + PvP tests/scratch; touch ~12 shared files for hunk restore; 1 forward migration; 2 automation modules corrected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Monorepo**: PASS — Delete `packages/pvp/` entirely; all Discord UI/jobs stay in `apps/discord_bot/`. No new package Discord imports.
- **Principle II — DB via RPC / atomic mutations**: PASS — Changelog claim/complete remain RPCs; vote reminders keep `claim_due_topgg_vote_reminders`; PvP removal uses one forward migration with `DROP … IF EXISTS` (no app-level multi-row loops).
- **Principle III — Typing / Pydantic**: PASS — Retain typed helpers in automation modules; no new untyped surfaces.
- **Principle IV — Slash commands**: PASS — No new slash commands; `/battle` restored to prior modes only.
- **Principle V — APScheduler**: PASS — Remove PvP matchmaker/ghost jobs; keep 30-minute Top.gg reminder job.
- **Principle VI — Error handling**: PASS — Changelog/channel failures stay logged + retryable; DM `Forbidden` → Store fallback; Top.gg errors back off without false eligibility.
- **Principle VII — YAGNI**: PASS — No redesign; delete PvP; fix two retained automations only.

**Post-design re-check**: Still PASS — contracts only redefine changelog key semantics and document reminder window authority; no speculative features.

## Project Structure

### Documentation (this feature)

```text
specs/056-shelve-pvp-automation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cleanup-inventory.md
│   ├── changelog-version-rpc.md
│   └── topgg-reminder-hardening.md
└── tasks.md                 # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
apps/discord_bot/
├── cogs/battle_cog.py              # RESTORE: Bot Battle + Friendly only
├── core/
│   ├── api_errors.py               # strip PvP error paths
│   ├── economy_rpc.py              # strip PvP economy hooks
│   ├── match_runs.py               # strip PvP run types
│   ├── match_recovery.py           # strip PvP recovery paths
│   ├── scheduler_jobs.py           # remove pvp_ghost_refresh_job
│   ├── deployment_changelog.py     # FIX: version-only claim key
│   ├── topgg_vote.py               # KEEP + harden schedule helpers
│   ├── pending_notices.py          # KEEP
│   ├── pvp_match.py                # DELETE
│   └── pvp_rpc.py                  # DELETE
├── embeds/pvp_embeds.py            # DELETE
├── views/pvp_queue_view.py         # DELETE
├── views/rivalries_view.py         # DELETE
├── tasks/
│   ├── pvp_matchmaker_job.py       # DELETE
│   └── topgg_vote_reminder_job.py  # KEEP
└── main.py                         # remove PvP jobs; keep reminder + changelog startup

packages/pvp/                       # DELETE entire package (+ requirements editable)

supabase/
├── migrations/
│   ├── 095–097_*.sql               # KEEP (Academy)
│   ├── 098–106_*.sql               # DELETE from repo (PvP era)
│   ├── 107_vote_reminders_and_changelog.sql  # KEEP
│   └── 108_shelve_pvp_and_version_changelog.sql  # NEW forward cleanup + version RPC
└── scripts/verify_required_schema.sql  # remove all PvP guard entries

tests/
├── test_deployment_changelog.py    # extend: version-only dedupe cases
├── test_topgg_vote_reminders.py    # extend: window/fallback/timing
└── test_pvp_*.py                   # DELETE

specs/053-pvp-matchmaking-rivalries/   # DELETE
specs/054-instant-pvp-backfill/        # DELETE
scratch/*pvp*, apply_migration_098–106, check_053_*, test_ai_*, …  # DELETE PvP tooling
```

**Structure Decision**: Stay inside existing monorepo layout. Cleanup is deletion + selective restore of shared files + one forward migration + two automation fixes. No new apps or packages.

## Complexity Tracking

> No Constitution Check violations.

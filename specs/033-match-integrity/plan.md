# Implementation Plan: Match Integrity & Concurrency (US-42.4)

**Branch**: `033-match-integrity` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/033-match-integrity/spec.md`

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: `030`, `031`, `032`

## Summary

Close Critical match integrity gaps without a new simulation engine: **settle-once** remains keyed by `match_run_id` / fixture history; **presentation retries must not abandon or re-pay**; **locks clear on all terminals**; **restart recovery** completes or abandons cleanly without stuck locks. Friendly stays sandbox (no coins/XP/evo). League sporting forfeits stay `026`.

**Technical approach**: (1) W0 audit already mapped callers — freeze in `contracts/match-path-audit.md`. (2) Reorder bot/league happy path: durable `complete_run` (and fixture marks) **before** Discord finalize; on present failure → present-retry only. (3) Migration **`077_match_integrity_guards.sql`**: `abandon_match_run` (status + release locks), optional `reconcile_orphaned_match_locks`. (4) Fix `match_recovery` bot path when rewards already applied; league play locks both humans; startup wipe replaced by targeted reconcile. (5) Tests for idempotency + recovery; `change_log` if managers see new copy.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `match_runs`, `match_locks`, `process_match_result`, `apply_match_economy`, `battle_cog`, `match_recovery`, `league_lifecycle_engine`, US-42.2/42.3 asserts

**Storage**: Extend existing `match_runs` / locks — no parallel match stack. Migration **077** adds recovery RPCs + verify guards. Next number after `076`.

**Testing**: Pytest for reward idempotency helpers / recovery classification; SQL/source greps (no Python `tick_evolution_match_progress`; friendly no economy); optional smoke double-settle

**Target Platform**: Discord bot (Render) + Supabase

**Project Type**: Monorepo integrity child (cogs/core + thin SQL recovery; optional tiny pure helper)

**Performance Goals**: Settlement remains one txn family per club; recovery O(active interrupted runs) at boot

**Constraints**: Constitution + US-42 — single XP/economy pipes; no new hubs; no `026` calendar rewrite; YAGNI — gap-fix ordering/recovery, don’t redesign stream UX

**Scale/Scope**: 1 migration; targeted battle/recovery/lifecycle patches; tests; no new slash commands

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Logic in packages/core; Discord presents |
| II. DB via RPC | PASS | Economy/XP via existing RPCs; new abandon/reconcile RPCs |
| III. Typing | PASS | Typed helpers |
| IV. Slash + defer | PASS | No new commands |
| V. APScheduler | PASS | Optional soft sweeper; boot recovery required |
| VI. Friendly errors | PASS | Clear already-settled / in-match copy |
| VII. YAGNI | PASS | Close Critical gaps only |

**Post-Phase 1 re-check**: PASS — contracts define settle/present/abandon APIs; no new packages required.

## Project Structure

### Documentation (this feature)

```text
specs/033-match-integrity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── match-run-lifecycle.md
│   ├── settle-once.md
│   ├── lock-and-abandon.md
│   ├── match-type-matrix.md
│   └── match-path-audit.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
supabase/migrations/077_match_integrity_guards.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_077.py
scratch/smoke_match_integrity_077.py

apps/discord_bot/core/match_recovery.py      # complete-if-rewarded; targeted lock reconcile
apps/discord_bot/cogs/battle_cog.py          # present-retry; no abandon-after-pay; league dual lock
apps/discord_bot/core/match_runs.py          # helpers if needed
apps/discord_bot/middleware/match_lock.py    # wrap new RPCs if useful
apps/discord_bot/main.py                    # recovery entry (already)

# Optional thin pure:
packages/match_engine/... or packages/player_engine/match_integrity.py
  classify_interrupted_run(rewards_applied, status) -> complete|abandon

tests/test_match_integrity_recovery.py
tests/test_match_integrity_sql_guards.py
# extend tests/test_match_xp.py / economy idempotency if needed
```

**Structure Decision**: Prefer fixing call-order + recovery RPCs over a monolithic `settle_match` mega-RPC. Economy/XP idempotency keys already exist — keep them; close status/lock/present gaps around them.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Waves

| Wave | Scope | Exit |
|------|-------|------|
| **W0** | Freeze audit in `match-path-audit.md` | Critical list agreed |
| **W1** MVP | Present-after-settle ordering; never abandon after successful rewards; dual league lock on play | SC-001/002/003 class |
| **W2** | Migration 077 `abandon_match_run` + lock reconcile; boot recovery uses it | Stuck lock / orphan paths |
| **W3** | Restart: bot complete-if-rewarded else abandon; league soft-stall harden | SC-005 |
| **W4** | Friendly matrix regression tests; changelog; Lock | Docs green |

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Decisions from codebase audit |
| [data-model.md](./data-model.md) | Run/lock/settlement entities |
| [contracts/](./contracts/) | Lifecycle, settle-once, abandon, type matrix, audit |
| [quickstart.md](./quickstart.md) | Validate W0–W4 |

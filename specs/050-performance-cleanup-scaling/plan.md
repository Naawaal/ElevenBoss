# Implementation Plan: Performance, Cleanup & Scalability Hardening

**Branch**: `050-performance-cleanup-scaling` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/050-performance-cleanup-scaling/spec.md` (US-46 working ID)

**US-42 / US-43 citation**: Extends US-43 (`038`) and hub waves `039`/`040`. Mutations stay on existing XP/economy RPC pipes (US-42.7 / 42.9). No parallel pipes; no sporting forfeit from infra. Match V2 retirement sequenced via `044` — never same deploy as Phase 2 hot-path RPCs.

## Summary

Turn ElevenBoss from multi-round-trip PostgREST hubs into **measured, page-sized, purpose-built reads** plus disposable caching — while deleting dead packages, fixing install/deps, and wiring observability. Foundations already exist (`AsyncClient` singleton, HTTP pool, `config_cache`, `perf_signals`, `get_game_config_many`, `job_claims` / `league_outbox`). This epic **extends** them.

**First ship focus (Phase 1 → Phase 2 start)**:
1. Extend `perf_signals` + Sentry + admin Performance panel + 24–72h baseline  
2. Delete `packages/training` + `packages/training_engine`; add `-e packages/energy`; split Alembic/ORM out of runtime deps  
3. `get_division_leaderboard_page` + `get_global_leaderboard_page` (replace unbounded division select)  
4. `browse_transfer_market` (replace fetch-50 / filter-in-Python)  
5. Then sell-eligibility + marketplace/development hub-state RPCs  

**Do not** raise HTTP connection pools before Phase 2 round-trip cuts. **Do not** introduce Redis/Celery in early phases.

## Technical Context

**Language/Version**: Python 3.11+ / PostgreSQL 15+ (Supabase)

**Primary Dependencies**: Existing `discord.py`, `supabase` async client (`apps/discord_bot/db/client.py`), `apscheduler`, Pydantic, `sentry-sdk` (wire only — already in requirements). No new message buses. Optional later: Redis behind `CacheBackend` (Phase 7 gate).

**Storage**: Forward migrations from **090+**. Reuse `league_operation_runs` / `job_claims.py` / `league_outbox`. Schema authority remains Supabase SQL migrations (not Alembic).

**Testing**: pytest structural/round-trip budget tests; SQL parity for page RPCs; load scripts under `scripts/load/` against staging/dev (never production Discord). Scratch EXPLAIN helpers for index gates.

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase; single instance default through Phase 6; multi-instance Phase 7 gated.

**Project Type**: Monorepo architecture/ops epic (apps + migrations + contracts; packages only for pure helpers if needed)

**Performance Goals**: Spec SLO table (light/normal/heavy hubs + mutation-after-defer); ≥50% round-trip cut on Phase 2 hot hubs (SC-002); ≥80% hit rate on Tier 1–2 cache after Phase 3 (SC-006)

**Constraints**: Constitution I–VII; AGENTS §§3/6–10; Principle II (no app-level `asyncpg`); defer immediately on slash commands; YAGNI — no Redis/Kafka/Celery/microservices in Phases 1–4; additive RPCs before deleting old Python paths

**Scale/Scope**: Hot paths: Division/Global leaderboard, Transfer Board, marketplace hub/sell, `/development` hub + skills/mentor, remaining config clusters (`get_pack_rarity_override`). Cleanup: `training`, `training_engine`, deps, Sentry, flag inventory. Deferred UX-neutral cog splits after Phase 2 stable.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Cache/retry/metrics/Sentry in `apps/discord_bot`; no `discord` in packages; delete unused packages only |
| II. DB via RPC / hosted client | PASS | New reads/mutations as thin RPCs or fewer PostgREST selects; ops `psycopg`/`asyncpg` stay in `requirements-ops.txt`, not bot runtime path |
| III. Typing / Pydantic | PASS | Typed page/cursor envelopes and cache backend protocol |
| IV. Slash + defer | PASS | No new slash commands; existing hubs; defer unchanged |
| V. APScheduler | PASS | Jobs must be claim-safe or single-worker before multi-instance; reuse `run_claimed_job` |
| VI. Friendly errors + observability | PASS | Sentry tags safe context only; admin Performance is owner-only |
| VII. YAGNI | PASS | Extend `perf_signals`/`config_cache`; Redis gated; no pool bump as first lever |

**Post-Phase 1 re-check**: PASS — contracts define RPC envelopes, cache tiers, budgets, and job rules without mandating Redis; V2 deletion gated; HTTP pool tuning deferred until after Phase 2 measurement.

## Project Structure

### Documentation (this feature)

```text
specs/050-performance-cleanup-scaling/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cache-policy.md
│   ├── round-trip-budgets.md
│   ├── observability.md
│   ├── cursor-pagination.md
│   └── job-idempotency.md
├── checklists/requirements.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
# Phase 1 — Cleanup & measurement
requirements.txt                          # + energy; - alembic/SQLAlchemy/Mako/greenlet; keep sentry
requirements-ops.txt                      # NEW — asyncpg/psycopg tooling if needed
requirements-dev.txt                      # NEW or extend — pytest stack if not already split
apps/discord_bot/core/perf_signals.py     # extend: per-command buckets, flush, p99, 429/5xx
apps/discord_bot/core/sentry_setup.py      # NEW — init if SENTRY_DSN
apps/discord_bot/main.py                   # call sentry_setup; instance id in logs
apps/discord_bot/cogs/admin_cog.py         # Performance panel (existing /admin only)
packages/training/                        # DELETE after rg gate
packages/training_engine/                 # DELETE after rg gate

# Phase 2 — Hot-path RPCs (additive; next free numbers after 089)
supabase/migrations/090_performance_read_rpcs.sql
  # get_division_leaderboard_page, get_global_leaderboard_page
  # browse_transfer_market, get_market_sell_eligible_cards
  # get_marketplace_hub_state, get_development_hub_state
  # get_skill_allocation_hub (+ mentor targets as needed)
supabase/migrations/091_leaderboard_cursor_indexes.sql   # after EXPLAIN
supabase/migrations/092_market_browse_rpc_indexes.sql     # after EXPLAIN
supabase/scripts/verify_required_schema.sql              # guard new RPCs/indexes

apps/discord_bot/cogs/leaderboard_cog.py                  # call page RPCs
apps/discord_bot/views/marketplace_transfer.py            # browse_transfer_market
apps/discord_bot/cogs/marketplace_cog.py                  # hub + sell RPCs
apps/discord_bot/cogs/development_cog.py                  # hub/skills/mentor reads
apps/discord_bot/core/economy_rpc.py                      # pack rarity → get_game_config_many

scripts/load/                                            # NEW suite (staging)
  profile_read.py, leaderboard_read.py, marketplace_browse.py,
  development_hub.py, mixed_workload.py

tests/test_leaderboard_page_budget.py
tests/test_market_browse_server_filter.py
tests/test_hub_round_trip_budgets.py

# Phase 3 — Cache abstraction
apps/discord_bot/core/cache/
  backend.py, memory.py          # Protocol + single-flight memory
  # redis.py                     # Phase 7 only
apps/discord_bot/core/config_cache.py   # become consumer of CacheBackend

# Phase 4 — Measured indexes + remaining cursor lists
supabase/migrations/093_measured_hot_indexes.sql

# Phase 5 — Flag maturity (separate deploys)
# Mentor env removal; V3 defaults; stop new V2; league mode consolidation

# Phase 6 — Durable async
supabase/migrations/094_job_outbox_hardening.sql
apps/discord_bot/core/job_claims.py / league_outbox.py   # generalize

# Phase 7 — Horizontal readiness (gated)
# AutoShardedBot design doc, RUN_SCHEDULER, optional Redis L2
```

**Structure Decision**: Stay in existing monorepo layout. Prefer **thin JSON RPCs** for multi-table reads over deep PostgREST embeds unless EXPLAIN proves otherwise. Extract `features/development/` modules only after Phase 2 RPCs are stable (maintainability, not a Phase 1 blocker). No new Discord slash surfaces — extend `/admin` Performance only.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

### Phase 1 — Cleanup & measurement

1. **Baseline**: Extend `perf_signals` per [contracts/observability.md](./contracts/observability.md); run 24–72h production capture; fill measured columns in [contracts/round-trip-budgets.md](./contracts/round-trip-budgets.md).
2. **Sentry**: `sentry_setup.init()` when `SENTRY_DSN` set; tags: command/hub, instance_id, guild_id, rpc_name, latency_class, error_category — never tokens/payloads.
3. **Admin Performance**: owner-only panel from `perf_signals.snapshot()` + job depth when available.
4. **Delete** `packages/training`, `packages/training_engine` after `rg` gates; fix/remove exclusive tests.
5. **`-e packages/energy`** in `requirements.txt`.
6. **Deps**: remove alembic/SQLAlchemy/Mako/greenlet from runtime after `rg` confirms no imports; move `asyncpg` to `requirements-ops.txt` if only scratch/migrations need it.
7. **Flag inventory** doc in research appendix / tasks note (Mentor, V3 keys, league flags) — no deletions in Phase 1.
8. **Top-query report**: scratch EXPLAIN candidates for division leaderboard + transfer listings (feeds Phase 4).

### Phase 2 — Hot-path DB reduction

1. Migration **090** additive RPCs (see Structure). Wire cogs to new RPCs; keep old path behind short fallback only if needed for rollback, then delete.
2. Leaderboard: replace unbounded `_division_embed` select; Global: replace top-100 + count pattern with page RPC + stable `(global_lp DESC, discord_id ASC)`.
3. Transfer Board: replace `_board_listings` fetch-50/Python filter with `browse_transfer_market`.
4. Sell + marketplace hub: one RPC each.
5. Development hub: **read-only** `get_development_hub_state` — do **not** fold `ensure_pending_legendary` into the read; keep mutation explicit.
6. Skills/mentor: consolidated read RPCs.
7. `get_pack_rarity_override` → `get_game_config_many`.
8. Structural tests for page size, server-side filter, RT budgets.
9. **HTTP pool**: leave 20/5; make env-configurable only; load-test after RT cuts.

### Phase 3 — Cache expansion

1. Introduce `CacheBackend`; migrate `config_cache` behind it.
2. Guild config, standings, leaderboard first-page, short profile-display TTLs per [contracts/cache-policy.md](./contracts/cache-policy.md).
3. Single-flight on memory backend.
4. Never cache mutation authority.

### Phase 4 — Indexes & remaining cursors

1. Rank queries by total time; EXPLAIN ANALYZE; Index Advisor.
2. Add only proven indexes (candidates in research); extend verify guards.
3. Cursor-paginate remaining growing lists (match history, sales log, admin history).

### Phase 5 — Feature-path consolidation (separate deploys)

1. Mentor: remove `_mentor_enabled` / env after soak confirmation.
2. Match V3: soak all three flags at 1 → default 1 → stop new V2 → drain → delete `v2_simulator` + branches.
3. League: audit dynamics vs automation vs lifecycle_v1; keep one authoritative path per responsibility (likely keep `auto_sim_expired_fixtures_job` if still required).

### Phase 6 — Durable async

1. Generalize job claim/outbox; move notification fanout/analytics/cleanup off interaction path.
2. Chunk season prizes; queue-depth in admin Performance.

### Phase 7 — Horizontal readiness

1. Document AutoShardedBot / multi-instance runbook.
2. `RUN_SCHEDULER` or all jobs claim-safe.
3. Optional Redis L2 behind same `CacheBackend`.

### Explicit non-goals this plan

- New gameplay slash commands / hubs  
- Raising pool size as Phase 1 “optimization”  
- Redis/Kafka/Celery/microservices in Phases 1–4  
- Caching coins/energy/ownership/locks  
- Deleting Match V2 in the same release as Phase 2 RPCs  
- Folding `energy` into `player_engine` (optional later)  
- Closing `049` DM ops inside this epic  

## Wave deploy pattern

```text
dev tests → apply additive migration → old bot still works → deploy new bot → measure → delete old Python path
```

Rollback = previous bot build; additive SQL functions remain harmless.

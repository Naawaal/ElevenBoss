# Implementation Plan: Database Scalability & Performance Architecture

**Branch**: `038-db-scalability-performance` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/038-db-scalability-performance/spec.md` (US-43; Clarifications 2026-07-22)

**US-42 citation**: Performance overlays on US-42.7 / 42.8 / 42.9 — no parallel coin/XP pipes; extends INV-08 via FR-006a.

## Summary

Make ElevenBoss command hubs fast and safe as concurrency grows by **measuring real bottlenecks**, cutting **N+1 / uncached config round-trips**, adding **proven indexes**, a **process-local TTL cache** for config (with multi-instance coherency gated to Phase 3), normalizing an **Idempotent Outcome Contract** (`applied` / `already_applied` + payload), light **retry + latency signals**, and only then introducing **job ownership / shared cache**. Principle II stays: mutations via thin RPCs; formulas in `packages/`.

**First ship focus (Phase 0–1)**: baseline → indexes → `game_config` TTL cache (+ optional batch getter) → consolidate `/development` hub + Training Drills + `/store` loads → query-plan snapshots → transient retry wrapper → in-process latency counters. Pack-claim idempotency + job locks are Phase 2–3.

## Technical Context

**Language/Version**: Python 3.11+ / PostgreSQL 15+ (Supabase)

**Primary Dependencies**: Existing `discord.py`, `supabase` async client (singleton in `apps/discord_bot/db/client.py`), `apscheduler`, Pydantic; **no new pip deps in Phase 0–1** (stdlib TTL dict — avoid `cachetools` unless justified later)

**Storage**: Existing Supabase schema; forward migrations from **080+**. Reuse `economy_ledger.idempotency_key`, `league_operation_runs` pattern for jobs. No `asyncpg` (Principle II / Clarification Q1).

**Testing**: pytest for cache TTL/invalidation, idempotent-outcome parser, round-trip counters (unit); migration/index guards; optional scratch EXPLAIN + hub smoke scripts

**Target Platform**: Discord bot on Render/Linux + hosted Supabase (plan-agnostic semantics)

**Project Type**: Monorepo architecture epic (apps + migrations + contracts; packages only if pure helpers needed)

**Performance Goals**: SC-001 ≤2s p95 hot hubs light load; SC-004 ≥50% remote round-trips on named hot paths; SC-002 / SC-006 deferred to Phase 2–3 drills

**Constraints**: Constitution I–VII; AGENTS Sections 3/7/8/10; FR-006a success-on-replay UX; FR-012 economy-tunable coherency under multi-instance; YAGNI — no Redis/sharding in Phase 0–1; no new slash commands

**Scale/Scope**: Single bot instance default through Phase 2; multi-instance Phase 3 gated. Hot-path catalog: `/development` hub, Training Drills menu, `/store`, `/profile`, `/squad`, `/league hub` (league auto-sim-on-open treated carefully — prefer not to worsen).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Cache/retry/metrics in `apps/discord_bot`; no `discord` in packages; pure helpers only if formulas needed |
| II. DB via RPC / hosted client | PASS | Clarification Q1 — Principle II kept; no application `asyncpg`; dashboard loads via RPC or fewer PostgREST selects |
| III. Typing / Pydantic | PASS | Typed cache keys, IdempotentOutcome parser models |
| IV. Slash + defer | PASS | Existing hubs; defer unchanged; no new commands |
| V. APScheduler | PASS | Phase 0–1 no multi-fire change; Phase 3 adds DB claim/lock before multi-instance |
| VI. Friendly errors | PASS | FR-006a forbids raw unique-constraint UX on replay |
| VII. YAGNI | PASS | Stdlib TTL cache first; Redis/workers gated; Complexity Tracking empty |

**Post-Phase 1 re-check**: PASS — contracts define envelopes and cache keys without mandating Redis; pack idempotency and job locks deferred with explicit gates; thin RPC rule preserved.

## Project Structure

### Documentation (this feature)

```text
specs/038-db-scalability-performance/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── hot-path-catalog.md
│   ├── idempotent-outcome.md
│   ├── cache-policy-and-keys.md
│   ├── query-plan-gate.md
│   └── observability-signals.md
├── checklists/requirements.md
└── tasks.md                # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
# Phase 0–1 (implement after /speckit.tasks)
supabase/migrations/080_scalability_indexes.sql          # NEW — measured indexes
supabase/migrations/081_game_config_batch.sql            # OPTIONAL — get_game_config_many
supabase/migrations/082_hub_dashboard_loads.sql          # OPTIONAL — consolidated hub RPCs
supabase/scripts/verify_required_schema.sql              # guard new RPCs/indexes as needed
scratch/baseline_hub_roundtrips.py                       # NEW — count awaits / latency
scratch/explain_hot_paths.py                             # NEW — EXPLAIN snapshots
scratch/apply_migration_080.py                           # ops pattern

apps/discord_bot/db/client.py                            # confirm singleton + close (already)
apps/discord_bot/core/config_cache.py                    # NEW — TTL process-local cache
apps/discord_bot/core/economy_rpc.py                     # route get_game_config* through cache
apps/discord_bot/core/db_retry.py                        # NEW — bounded backoff for transient errors
apps/discord_bot/core/idempotent_outcome.py              # NEW — normalize replay → already_applied
apps/discord_bot/core/perf_signals.py                    # NEW — in-process latency / round-trip counters
apps/discord_bot/cogs/development_cog.py                 # hub + training menu consolidation
apps/discord_bot/cogs/store_cog.py                       # store hub consolidation
apps/discord_bot/main.py                                 # optional admin/stats exposure hook (existing surface only)

tests/test_config_cache.py
tests/test_idempotent_outcome.py
tests/test_db_retry.py

# Phase 2+
supabase/migrations/08x_pack_claim_idempotency.sql
# claim_daily_pack + FR-006a envelope

# Phase 3+
supabase/migrations/08y_job_claim_locks.sql              # scheduler single-owner
# shared cache adapter — only when multi-instance approved
```

**Structure Decision**: Stay inside existing monorepo layout. Prefer **cache + batch config + selective dashboard RPCs** over deep PostgREST embedding for Phase 1 (embedding allowed only with query-plan gate). No new Discord slash surfaces; operator signals via existing admin/health patterns or ephemeral admin command only if already present — otherwise log-based counters first (YAGNI).

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

### Phase 0 — Measure

1. Script `scratch/baseline_hub_roundtrips.py` (or pytest markers) to record round-trip counts and wall time for: `show_hub`, `show_training_menu`, `show_store`, `show_profile`, `fetch_squad_data`, `league_hub` (without forcing auto-sim if avoidable).
2. Document baseline numbers in `contracts/hot-path-catalog.md` (fill measured columns).
3. Confirm `get_client()` singleton is the only production path (grep `acreate_client`).

### Phase 1 — No-regret

1. **Migration 080 indexes** (adjust after EXPLAIN; candidates from research):
   - `league_fixtures (season_id, matchday)` and/or partial `(season_id) WHERE is_played = false`
   - `economy_ledger (club_id, created_at DESC)` if club ledger scans appear
   - Only ship indexes with before/after plan evidence (`contracts/query-plan-gate.md`).
2. **`config_cache`**: process-local TTL (~5 min) for `get_game_config` / `_int` / `_numeric`; invalidate-on-write helper for admin/config updates when those paths exist; economy-priced keys listed in cache contract.
3. **Optional `get_game_config_many`**: one RPC returning `jsonb` map of keys — cold-cache fill for drills menu (5 keys → 1 call).
4. **Hub consolidation** (pick minimum for SC-004):
   - Training Drills: cached/batch config + avoid duplicate energy sync if hub already synced.
   - `/development` hub: collapse legendary/rewards/energy where safe into fewer calls or one RPC.
   - Prefer RPC JSON dashboard over deep `select('*, nested(*)')` unless EXPLAIN proves nested is cheaper.
5. **`idempotent_outcome` adapter**: map economy `replay: true` → status `already_applied`; map first success → `applied`; use in new/touched mutation UIs.
6. **`db_retry`**: wrap transient failures (timeouts / 5xx / connection) with jittered backoff; **do not** retry non-idempotent mutations without FR-006 key.
7. **`perf_signals`**: `perf_counter` around hot hub entrypoints; expose via structured logs; optional `/bot` stats only if an admin surface already exists.
8. Tests for cache TTL, invalidation, outcome parser, retry bounds.

### Phase 2 — Integrity & lists

1. Gap list from US-42 map + research: **`claim_daily_pack` lacks idempotency_key** — add key + FR-006a envelope.
2. Normalize remaining mutation RPCs touched by performance work to FR-006a (additive JSON fields OK).
3. Cursor pagination for market/leaderboard if OFFSET pain measured.
4. Operator alert thresholds documented (even if alerts = log watch initially).

### Phase 3 — Multi-instance

1. **Job claim**: generalize `league_operation_runs`-style unique `operation_key` (or `job_claims` table / advisory lock) so each scheduled durable job runs once across processes.
2. **Economy tunables**: shared cache **or** pub-sub invalidation (Clarification Q2) — Cache Key Catalog required first.
3. Do not enable multi-instance deploy until SC-006 drill defined and green.

### Explicit non-goals this plan

- Amending constitution for `asyncpg`
- Redis in Phase 0–1
- Write-behind for coins/XP
- Sharding / read replicas until Phase 4 gate

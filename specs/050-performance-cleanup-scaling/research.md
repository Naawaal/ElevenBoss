# Research: Performance, Cleanup & Scalability Hardening

**Feature**: `050-performance-cleanup-scaling` | **Date**: 2026-07-31  
**Parent**: [plan.md](./plan.md) | [spec.md](./spec.md)

All Technical Context unknowns resolved against the live repo (post-`038`/`039`/`040` / migration `089`).

---

## R1 — Extend existing foundations vs rewrite clients

**Decision**: Extend singleton Supabase `AsyncClient`, shared `httpx` pool (20/5), `config_cache`, `perf_signals`, `get_game_config_many`, `job_claims` / `league_outbox`. Do not create a second DB client or monitoring framework.

**Rationale**: Spec §2 and constitution Principle II; “create persistent client” is already solved. Raising pool size before cutting queries would amplify Free-tier pressure.

**Alternatives considered**: New Redis-first stack (rejected until multi-instance/load justifies); raw `asyncpg` in app (constitution violation); Celery (YAGNI).

---

## R2 — Leaderboard: full division load

**Decision**: Replace `leaderboard_cog._division_embed` unbounded `players` select with RPC `get_division_leaderboard_page(division, viewer_id, cursor, page_size)` returning page rows + viewer rank + totals + promo/releg cutoffs + cursors. Global: `get_global_leaderboard_page` with `(global_lp DESC, discord_id ASC)`.

**Rationale**: Confirmed full-division fetch with in-Python `paginate_rows` (10/page). Global already limits 100 but may second-query for rank — still not keyset-complete.

**Alternatives considered**: PostgREST `.range()` only (still needs rank/cutoffs computed; weaker for promo bands); OFFSET pages (rejected — grows expensive).

---

## R3 — Transfer Board: fetch-50 then Python filter

**Decision**: RPC `browse_transfer_market(...filters, sort_mode, cursor, limit)` filters/sorts in Postgres; return exactly UI page size (25).

**Rationale**: `marketplace_transfer._board_listings` documents upgrade path; current model is incomplete at scale (best match may sit outside first 50).

**Alternatives considered**: Raise fetch limit to 500 (worse egress, still incomplete); client-side only (status quo).

---

## R4 — Marketplace sell / hub / development hub

**Decision**:
- `get_market_sell_eligible_cards(owner_id)` replaces 5-way gather + Python exclude.
- `get_marketplace_hub_state(owner_id)` collapses player + flag + listing count/cap.
- `get_development_hub_state(owner_id)` is **read-only**; keep `ensure_pending_legendary` / claim flows as explicit mutations.
- Skills/mentor: dedicated read RPCs returning roster summary + selected/eligible targets.

**Rationale**: Spec FR-014–017; hub open must not mutate as a side effect of “read state.”

**Alternatives considered**: Deep PostgREST embeds (harder budgets/EXPLAIN); folding legendary ensure into hub read (rejected — non-idempotent surprise).

---

## R5 — Cleanup packages & dependencies

**Decision**: Delete `packages/training` and `packages/training_engine` after `rg` shows no app imports. Add `-e packages/energy`. Remove alembic/SQLAlchemy/Mako/greenlet from production `requirements.txt` after import verification. Keep `sentry-sdk`. Move `asyncpg` to `requirements-ops.txt` if only scratch/migration tooling needs it.

**Rationale**: Repo confirms unused training packages; energy imported by `store_cog` but missing from editable installs; Alembic contradicts constitution schema authority; Sentry present but uninitialized.

**Alternatives considered**: Fold energy into `player_engine` immediately (deferred optional); keep Alembic “just in case” (rejected).

---

## R6 — Observability: perf_signals + Sentry + admin

**Decision**: Extend `perf_signals` with per-command 1-minute buckets (p50/p95/p99, RTs, retries, 429/5xx, cache stats), periodic flush/log, owner-only `/admin` Performance panel. Initialize Sentry when `SENTRY_DSN` set with safe tags only.

**Rationale**: Spec FR-001–005; avoid per-command DB metric rows (Free 500 MB).

**Alternatives considered**: External APM only (Sentry complements, does not replace in-process budgets); writing one ledger row per command (rejected).

---

## R7 — Cache abstraction timing

**Decision**: Introduce `CacheBackend` **after** Phase 2 query shaping. Migrate `config_cache` behind it; add guild/standings/first-page/profile-display tiers + single-flight. Redis = Phase 7 optional L2.

**Rationale**: Caching a full-division read hides the bug; spec §60 step 6.

**Alternatives considered**: Redis in Phase 1 (rejected — YAGNI, multi-instance not live).

---

## R8 — Indexes

**Decision** (measured 2026-07-31 via `scratch/explain_050_hot_paths.py`):

| Index | Migration | Evidence | Outcome |
|-------|-----------|----------|---------|
| `idx_players_global_lp_human` | 091 | Seq Scan + Sort on global window | Index Only Scan when forced; planner may seqscan at ~30 humans |
| `idx_players_division_lb_human` | 091 | Division Index + Sort | After 092: Index Only Scan, **no Sort** (0.088 ms) |
| Drop `idx_players_division` | 092 | Bare index stole plans from composite | Required for ordered LB scan |
| `idx_league_fixtures_season_played` | 091 | Bitmap season + Filter removed 56/56 | Index Scan 1.45→0.13 ms |
| Market browse sorts | — | `transfer_listings_status_expires_idx` already; Sort of 6 actives | **Waived (T036)** |
| `player_cards` owner composites | — | `idx_player_cards_owner` + anti-joins indexed | **Waived** |
| skills/mentor/hub | — | PK / owner / seller_status already | **Waived** |

Snapshots: `scratch/explain_snapshots/20260731T142205Z_050_*` (before), `…142345Z…` (after 091), `20260731_after092_*` (after 092).

**Rationale**: Spec FR-036 — no index without EXPLAIN.

---

## R9 — Retry & mutation safety

**Decision**: Central `db_retry` for safe reads (429/502/503/504/timeout) with jittered backoff. Mutations retry only with durable idempotency keys (`apply_club_economy`, claim runs, etc.).

**Rationale**: Spec FR-026; aligns with `038` idempotent-outcome contract.

---

## R10 — Feature flags & Match V2

**Decision**: Phase 1 = inventory only. Phase 5 (separate deploys): Mentor env removal after soak; V3 all modes `1` soak → default `1` → stop new V2 → drain → delete `v2_simulator` + cog branches. League: audit `league_dynamics_enabled` / `league_automation_enabled` vs lifecycle_v1 jobs (`league_state_machine_job`, `league_lifecycle_wake_job`, `auto_sim_expired_fixtures_job`) before deleting any.

**Rationale**: Spec FR-031–033; `resolve_engine_version` still defaults V3 flags to `0`.

---

## R11 — Background work boundary

**Decision**: Do not move core match settlement (result, lock release, coins/XP, fatigue/injury, fixture result) solely to APScheduler. Use durable outbox for notifications/analytics/cleanup/chunked prizes. Prefer distributed-safe claims over process-only `asyncio.create_task`.

**Rationale**: Spec FR-027–029; existing `run_claimed_job` pattern.

---

## R12 — Migration numbering

**Decision**: `090` read RPCs → `091` measured indexes → `092` drop bare division index → `093` hub-state RPCs (already shipped) → next free **`094+`** for outbox/jobs.

---
**Rationale**: Schema Rule / AGENTS §8.

---

## R13 — Load testing

**Decision**: `scripts/load/*` hits staging/dev RPC/helpers — never production Discord gateway. Escalate 10→1000 concurrent until saturation knee; mixed workload ~30% profile/squad, 20% development, 15% leaderboard, 15% market, 10% league, 5% match setup, 5% mutations.

**Rationale**: Spec FR-035 / §47–49.

---

## Open items deferred to tasks (not NEEDS CLARIFICATION)

- Exact V3 soak duration (ops note at Phase 5 start)
- Whether `auto_sim_expired_fixtures_job` remains after lifecycle wake audit (trace-driven)
- Precise admin Performance embed layout (owner-only; YAGNI)

---

## Appendix: Feature-flag inventory (T001 — 2026-07-31)

| Flag / job | Location | Notes |
|------------|----------|-------|
| `MENTOR_TRANSFUSION_ENABLED` | `apps/discord_bot/cogs/development_cog.py` `_mentor_enabled` (~L78) | Env, default on |
| `match_engine_v3_bot/league/friendly` | `apps/discord_bot/core/match_runs.py` `resolve_engine_version` (~L25–28) | `game_config` int, default 0 → V2 |
| `league_dynamics_enabled` | `apps/discord_bot/core/economy_rpc.py` (~L314); used in `league_automation.py` | RPC + config fallback |
| `league_automation_enabled` | `economy_rpc.py` (~L336); `guild_config.league_automation_enabled` | Global + per-guild |
| `league_state_machine_job` | `main.py` cron; `scheduler_jobs.py` → `run_league_state_machine` | Claimed |
| `league_lifecycle_wake_job` | `main.py` interval 5m | Lifecycle wake |
| `auto_sim_expired_fixtures_job` | `main.py` interval 10m; `league_cog.auto_sim_expired_fixtures` | Still scheduled |

## Appendix: training import gate (T004)

`rg` over apps/packages/tests/scripts/scratch: no live `import training` / `training_engine` app usage (only self-refs inside deleted packages + comment in `progression.py`). Packages deleted in implement MVP-A.

## Appendix: baseline note (T016)

Start 24–72h production capture after deploy of extended `perf_signals` + admin Performance panel. Window start: deploy time of MVP-A bot.

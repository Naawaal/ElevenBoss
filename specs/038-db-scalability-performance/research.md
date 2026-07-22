# Research: Database Scalability & Performance (US-43)

**Feature**: `038-db-scalability-performance` | **Date**: 2026-07-22

Resolves Technical Context unknowns and records decisions for `/speckit.plan` Phase 0.

---

## R1 — True capacity bottlenecks (not Free-tier REST cap)

**Decision**: Treat connection-pool pressure, CPU/IO, Auth/gateway limits, and **application N+1 / uncached config RPCs** as primary risks. Do not plan around a false “2 req/s Data API” Free-tier cap.

**Rationale**: Spec §0.4 + peer review; hosted Data API request volume is not the claimed bottleneck. Codebase shows hubs issuing 4–11 sequential PostgREST/RPC calls with **zero** `game_config` TTL cache.

**Alternatives considered**: Optimize solely for REST rate limits — rejected (wrong diagnosis).

---

## R2 — Hot-path priority order

**Decision**: Phase 1 hot paths (SC-004 targets), in order:

1. `/development` → Training Drills menu (`show_training_menu`) — ~10–11 calls, **5×** uncached `get_game_config_int`
2. `/development` hub (`show_hub`) — ~5–8 calls
3. `/store` hub — ~4 calls with duplicate config via energy formatter
4. `/profile`, `/squad` — secondary if budget remains
5. `/league hub` — measure carefully; avoid coupling performance work to `auto_sim_expired_fixtures` side effects on open

**Rationale**: Highest sequential config spam + manager frequency; largest round-trip win from cache alone.

**Alternatives considered**: Start with league hub — rejected (variable call count, sim-on-open side effects). Full-repo rewrite — rejected (YAGNI).

---

## R3 — Caching approach (Phase 0–1 vs multi-instance)

**Decision**:

| Phase | Mechanism |
|-------|-----------|
| 0–1 (single instance) | Process-local TTL dict (~5 min) for `game_config*` in `apps/discord_bot/core/config_cache.py`; no new pip dependency |
| Multi-instance (Phase 3) | Economy-priced tunables: **shared cache or active invalidation** (Clarification Q2); non-priced flags may stay local |

**Rationale**: Spec FR-009–012; constitution VII (no Redis until needed); Clarification Q2 forbids TTL-only local economy prices under multi-instance.

**Alternatives considered**: Redis from day one — deferred. Never cache config — rejected (leaves 5 RPC drills tax). `cachetools` dependency — unnecessary if stdlib TTL dict suffices.

---

## R4 — Round-trip consolidation style

**Decision**: Prefer **(a)** config cache + optional **`get_game_config_many`**, then **(b)** thin **dashboard RPCs** returning JSON for hub payloads. Use PostgREST resource embedding only when `EXPLAIN` shows it beats N+1 **and** indexes exist (`contracts/query-plan-gate.md`).

**Rationale**: Deep nested selects become LATERAL joins and can regress without FK indexes (peer review). Existing bot already favors RPCs for mutations; read dashboards fit Principle II.

**Alternatives considered**: `asyncio.gather` only — improves wall clock but **fails SC-004** (same request count). Unverified deep embeds — rejected.

---

## R5 — Idempotent Outcome Contract vs existing `replay`

**Decision**: Adopt FR-006a statuses `applied` | `already_applied` + result payload for **new/touched** mutation surfaces. Adapter maps existing economy JSON `replay: true` → `already_applied` without forcing a big-bang rewrite of every RPC in Phase 1.

**Rationale**: Clarification Q3; `apply_club_economy` already returns `replay` (mig 055/038). Pack claim (`claim_daily_pack`) lacks `p_idempotency_key` — Phase 2 gap.

**Alternatives considered**: Raise on unique violation and map in Python — rejected (manager may see 500). Require every historical RPC rewritten in Phase 1 — rejected (scope).

---

## R6 — Index candidates

**Decision**: Ship indexes only after EXPLAIN on real queries. **Candidates**:

- `league_fixtures (season_id, matchday)` and/or partial unplayed
- `economy_ledger (club_id, created_at DESC)` for club ledger scans
- Verify `player_cards` owner indexes already sufficient (`idx_player_cards_owner`, partial active)

**Rationale**: Exploration found no dedicated `league_fixtures` secondary indexes; ledger unique on idempotency_key only.

**Alternatives considered**: Speculative indexes on every FK — rejected (FR-020 / write amplification).

---

## R7 — Retry / client lifecycle

**Decision**: Keep **singleton** `acreate_client` (`db/client.py`). Add bounded retry with jitter for **transient** transport/5xx on **safe reads** and **idempotent** mutations only. Discord 429 handling already exists separately — do not conflate.

**Rationale**: Spec FR-013/014; no Supabase retry today; Discord-only backoff exists in views/battle.

**Alternatives considered**: Retry all mutations — rejected (double-apply risk without FR-006). New client per command — rejected (FR-013).

---

## R8 — Observability (Phase 1 minimal)

**Decision**: In-process counters + structured logs for hub wall time and remote round-trip counts (`perf_signals`). Alert thresholds documented; wire to external APM only if already in ops stack (none today — health endpoint is status-only).

**Rationale**: FR-017/018; YAGNI vs Prometheus from day one.

**Alternatives considered**: Full OpenTelemetry — deferred. No metrics until Phase 2 — rejected (cannot prove SC-001/004).

---

## R9 — Scheduler multi-instance

**Decision**: Phase 0–2 remain single-process. Phase 3: database-backed job claim (extend `league_operation_runs` pattern or `job_claims` + unique `operation_key`). Advisory locks acceptable alternative in plan tasks.

**Rationale**: Spec FR-016; today 12 DB-writing jobs with **no** global leader election; only league lifecycle has per-op leases.

**Alternatives considered**: Redis lock in Phase 1 — deferred. Dedicated worker process — Phase 3 option, not required if claim table works.

---

## R10 — Principle II / PL/pgSQL bound

**Decision**: Confirmed Clarification Q1 — no constitution amendment. Dashboard RPCs stay thin (assemble rows / JSON). Price/formula logic stays in packages where already required (US-23/25).

**Rationale**: Spec §0.6; existing economy/progression pipes.

**Alternatives considered**: `asyncpg` transactions in Python — rejected for this epic.

---

## Open items deferred to tasks (not blocking plan)

- Exact measured baselines (fill hot-path catalog during Phase 0 implement)
- Whether `/bot stats` admin surface exists vs logs-only
- Final index DDL after first EXPLAIN pass

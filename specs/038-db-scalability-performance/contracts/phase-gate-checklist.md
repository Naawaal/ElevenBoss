# Contract: Phase Gate Checklist (US-43)

**Parent**: [../spec.md](../spec.md) | [../plan.md](../plan.md)

Use before enabling Phase 2+ / multi-instance complexity.

## Phase 1 exit (MVP) — required before claiming US1 done

- [x] HP-1/HP-2 baselines recorded in hot-path catalog
- [x] Config TTL cache + `get_game_config_many` shipped
- [x] Indexes 080 applied (with EXPLAIN snapshots)
- [x] Hub consolidation + `perf_signals` on HP-1…HP-3
- [ ] Live p95 ≤2s under light load (ops validate in Discord)

## Phase 2 unlock

- [x] Pack claim FR-006a + idempotency key (US3 / mig 082)
- [ ] SC-001/SC-004 evidenced in production-like Discord env (ops)
- [ ] Cursor pagination only if OFFSET pain measured

## Phase 3 unlock (multi-instance)

- [ ] SC-002 concurrency drill defined and run
- [x] Job claim helpers + catalog scheduler jobs wrapped (US5) — see `job-claim-catalog.md`
- [ ] SC-006 two-process drill green (unit stand-in shipped; live two-process still required)
- [ ] Economy-priced `cfg:*` use shared cache or active invalidation (FR-012) — **not** TTL-only local
  - [x] Process-local `invalidate_game_config` / `invalidate_priced_game_config` helpers shipped (`economy_rpc.py`)
  - [ ] Shared backend or cross-instance broadcast still required before multi-instance
- [x] Cache Key Catalog priced tags complete
- [ ] Redis / shared backend justified by failed Phase 1–2 metrics (YAGNI)

## Phase 4

- [ ] Read replicas / sharding — written decision record only after measured need

## Hard rejects until gates pass

- Constitution Principle II amendment / application `asyncpg`
- Write-behind for coins/XP/ownership
- New slash commands for “performance UI”

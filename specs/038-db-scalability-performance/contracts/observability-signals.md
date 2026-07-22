# Contract: Observability Signals (FR-017 / FR-018)

**Parent**: [../spec.md](../spec.md)

## Phase 1 signals (minimum)

| Signal | How | Consumer |
|--------|-----|----------|
| Hub wall time (ms) | `perf_counter` around HP-1…HP-3 | Structured log `perf.hub` |
| Remote round-trips / invocation | Counter incremented in thin DB wrapper or manual marks | Log + SC-004 evidence |
| Cache hit / miss | `config_cache` counters | Log `perf.cache` |
| Transient retry count | `db_retry` | Log `perf.retry` |
| Data-access errors | Existing logging + error counter | Ops |

## Alert thresholds (initial)

| Condition | Threshold | First response |
|-----------|-----------|----------------|
| Hot-hub p95 (rolling) | > 2s light / > 3s busy | Check cache hit rate + Supabase CPU/pool |
| Retry rate | > 5% of hub calls over 5 min | Check connectivity / pool; freeze deploys |
| Cache hit rate (cfg) after warm | < 70% | Investigate TTL thrash / missing keys |
| Error rate on hubs | > 1% over 5 min | Check logs; fail closed |

External paging optional; documenting + log-based watch satisfies Phase 1. Phase 2 may wire hosting alerts.

## Non-goals Phase 1

- Full distributed tracing
- Discord-visible metrics for all managers (admin-only if surface exists)

## Log-only watch procedure (no admin slash surface)

No dedicated `/bot stats` command exists. Operators:

1. Grep bot logs for `perf.hub`, `perf.cache`, `perf.retry` (Render / host log stream).
2. After warming `/development` Training Drills twice, expect `perf.cache` hit_rate rising and second hub `ms` lower.
3. Compare thresholds in `apps/discord_bot/core/perf_signals.py` (`HUB_P95_LIGHT_MS=2000`, `HUB_P95_BUSY_MS=3000`, `CACHE_HIT_RATE_MIN=0.70`) to this table.
4. Optional: call `perf_signals.snapshot()` from a one-off scratch script against a running process is **not** supported (in-process only) — rely on logs.

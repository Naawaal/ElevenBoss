# Contract: Observability

**Parent**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)  
**Related**: `038` [observability-signals.md](../../038-db-scalability-performance/contracts/observability-signals.md)

## Process signals (`perf_signals`)

Extend existing module; do not fork a second framework.

| Signal | Requirement |
|--------|-------------|
| Per hub/command | count, p50, p95, p99, errors |
| Data plane | round_trips, retries |
| Upstream classes | 429 count, 5xx count |
| Cache | hits, misses, hit_rate, entry count |
| Scheduler/jobs | failure count; queue depth / oldest pending when outbox exists |
| Identity | `instance_id` on snapshots/logs |

Storage: **1-minute in-memory buckets**; flush to structured logs (and optional short-retention aggregate table later). Never one DB row per command.

## Sentry

| Rule | Detail |
|------|--------|
| Init | Only if `SENTRY_DSN` set |
| Tags | command/hub, instance_id, guild_id, rpc_name, latency_class, error_category |
| Forbidden | tokens, passwords, full card/economy payloads, Authorization headers |

## Admin Performance panel

- Extend existing **owner-only** `/admin` (no new public slash command)
- Show: uptime, instance_id, request volume, p50/p95, round trips, retries, 429/5xx, cache hit rate, scheduler/job health

## Baseline window

Capture **24–72 hours** production before declaring Phase 2 success (FR-001 / SC-001).

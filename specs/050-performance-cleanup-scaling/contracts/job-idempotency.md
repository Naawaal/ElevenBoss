# Contract: Job Idempotency & Background Work

**Parent**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)  
**Related**: `038` [job-claim-catalog.md](../../038-db-scalability-performance/contracts/job-claim-catalog.md)

## Principles

1. Important background work is **durable** (DB queue/outbox), not only `asyncio.create_task`.
2. Every scheduler job is **distributed-safe** (claim/lock/idempotency) **or** explicitly single-worker (`RUN_SCHEDULER=1`).
3. Prefer generalizing `job_claims.run_claimed_job` / `league_outbox` over new brokers.

## Safe to move off interaction path

- Discord notification fanout  
- League journal / analytics / market metrics  
- Historical rollups, expired cleanup  
- Chunked season prize batches (50–200 clubs per claim)  
- Non-critical audit summaries  

## Must stay synchronous with “match complete”

- Result persistence  
- Match lock release  
- Coins/rewards + XP when gameplay depends on them  
- Fatigue/injury state  
- League fixture result  

Prefer one atomic settle-style RPC if currently fragmented — do not “fix latency” by racing managers into half-settled state.

## Claim envelope

| Field | Rule |
|-------|------|
| `idempotency_key` | Unique per logical unit; replays return already-applied / no-op |
| `claimed_by` | Instance id |
| `attempt_count` / `last_error` | Observability |
| `available_at` | Backoff for retries |

## Mutation retry rule

- **Reads**: jittered backoff on 429/502/503/504/timeout  
- **Mutations**: retry only with durable idempotency identity; uncertain timeout ≠ safe retry  

## Multi-instance gate (Phase 7)

Before multiple bot processes in production: checklist in spec FR-030 (idempotent mutations, no process-only business truth, claim-safe jobs, instance-tagged metrics, sharding plan documented).

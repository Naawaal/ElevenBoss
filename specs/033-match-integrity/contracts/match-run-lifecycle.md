# Contract: Match Run Lifecycle

**Feature**: US-42.4

## Normative transitions

```text
start → streaming (+ locks)
streaming → completing (optional)
completing|streaming → completed  (after rewards durable)
completing|streaming → abandoned|failed  (no new rewards; locks cleared)
completed → present retry (Discord only)
```

## Rules

1. Never `abandoned` after successful reward application for that run — use `completed`.
2. Never leave human `match_locks` after terminal `completed|abandoned|failed` without reconcile.
3. Friendly may use locks for concurrency but never enters economy/XP/evo settlement.

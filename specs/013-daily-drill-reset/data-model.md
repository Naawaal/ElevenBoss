# Data Model: Daily Drill Cap Desync

**Schema impact**: No new tables/columns. RPC body + optional repair function.

## Existing entities

| Object | Role |
|--------|------|
| `players.daily_drill_count` | Club uses for current reset day |
| `players.daily_drill_reset_at` | DATE of last soft-reset day (UTC) |
| `player_drill_daily_log (card_id, drill_date, count)` | Per-card daily uses |
| Cap constants | Club 20; per-card 5 (RPC constants, not columns) |

## Effective display / gate rule

```text
effective_count =
  0  if reset_at is null OR reset_at < today_utc
  else max(0, daily_drill_count)
```

Club allow if `effective_count < 20`.

## Repair rule (idempotent)

For each player row:

```text
log_sum = COALESCE(SUM(log.count) for owned cards, drill_date = today), 0)
log_sum = LEAST(20, log_sum)

if reset_at is null OR reset_at < today:
    set count = 0, reset_at = today   # or count = log_sum (usually 0)
elif count <> log_sum:
    set count = log_sum, reset_at = today
```

Prefer: always `count = log_sum` and `reset_at = today` when repairing (single assignment) — healthy clubs where count already equals log_sum are no-ops.

## RPC result (unchanged shape)

`process_stat_drill` / `process_recovery_session` continue returning `daily_drill_count` after increment for clients that read it.

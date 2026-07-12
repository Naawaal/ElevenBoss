# Quickstart: Daily Drill Cap Desync

## Prerequisites

- Branch `013-daily-drill-reset`
- `DATABASE_URL` for apply/repair
- Bisup bot redeploy after Python changes

## Apply

```powershell
python scratch/apply_migration_058.py
python scratch/repair_daily_drill_counts.py   # or RPC invoke inside apply
pytest tests/test_api_errors.py tests/test_drill_caps.py -q
```

## Verify stuck club (example)

```sql
SELECT discord_id, daily_drill_count, daily_drill_reset_at, CURRENT_DATE AS today
FROM players
WHERE discord_id = 976054227459776582;

SELECT COALESCE(SUM(l.count), 0) AS log_sum_today
FROM player_drill_daily_log l
JOIN player_cards c ON c.id = l.card_id
WHERE c.owner_id = 976054227459776582
  AND l.drill_date = CURRENT_DATE;
```

## Manual one-club unblock (if needed before full repair)

```sql
-- Prefer repair RPC; blind zero only if log_sum_today = 0
UPDATE players
SET daily_drill_count = 0,
    daily_drill_reset_at = CURRENT_DATE
WHERE discord_id = 976054227459776582
  AND daily_drill_reset_at < CURRENT_DATE;
```

## Deploy order

1. Apply `058` + repair on Supabase  
2. `git pull` on Bisup + `systemctl restart elevenboss` (api_errors + hub display)

# Contract: repair_daily_drill_counts

**Migration**: `058_daily_drill_cap_desync.sql`  
**Signature**: `public.repair_daily_drill_counts() RETURNS JSONB`

## Behavior

For every `players` row (or only those with `daily_drill_count > 0 OR reset_at IS DISTINCT FROM CURRENT_DATE`):

1. `log_sum := LEAST(20, COALESCE((
     SELECT SUM(l.count)::int FROM player_drill_daily_log l
     JOIN player_cards c ON c.id = l.card_id
     WHERE c.owner_id = players.discord_id AND l.drill_date = CURRENT_DATE
   ), 0))`
2. `new_count := log_sum` when `reset_at IS NULL OR reset_at < CURRENT_DATE OR daily_drill_count IS DISTINCT FROM log_sum` with special case: if reset before today, `new_count := log_sum` (typically 0).
3. UPDATE when changed: `daily_drill_count = new_count`, `daily_drill_reset_at = CURRENT_DATE`.

Return `{ "updated": N, "checked": M }`.

## Ops

- `scratch/apply_migration_058.py` applies SQL then `SELECT repair_daily_drill_counts()`
- `scratch/repair_daily_drill_counts.py` can re-invoke alone

## Safety

- Never set count below today’s log_sum  
- Never set count above 20  
- Idempotent second run → `updated = 0`  

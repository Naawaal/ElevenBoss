# Contract: `process_weekly_payroll`

**Feature**: 019 | **Migration**: 063

## RPC (preferred signatures)

### Batch entry (scheduler)

```sql
process_weekly_payroll(p_week_key TEXT DEFAULT NULL) RETURNS JSONB
```

- Resolves `week_key` = UTC ISO week if null.  
- If NOT `wages_payroll_enabled()` → return `{ processed: 0, reason: "flag_off" }` without mutating coins.  
- Iterates human clubs (`is_ai = false`) lacking a `payroll_runs` row for `week_key`, calling the per-club body.  
- Set-based preferred over N separate HTTP RPCs from the bot when possible.

### Per-club body (also callable for smoke)

```sql
process_club_weekly_payroll(p_club_id BIGINT, p_week_key TEXT) RETURNS JSONB
```

**Returns** (shape illustrative):

```json
{
  "status": "paid|partial|skipped_ai|skipped_flag|skipped_zero",
  "week_key": "2026-W29",
  "bill_coins": 1200,
  "debt_before": 0,
  "paid_coins": 1200,
  "debt_after": 0,
  "strikes_after": 0,
  "coins_after": 5000
}
```

## Algorithm

1. Lock club row (`SELECT … FOR UPDATE` on `players`).  
2. If flag off → `skipped_flag`. If `is_ai` → `skipped_ai`.  
3. If `payroll_runs` exists for `(club_id, week_key)` → return existing (idempotent).  
4. Load XI via `squad_assignments` + `player_cards`; compute `bill` (see wage-formula) × scale.  
5. `obligation = payroll_debt + bill`.  
6. If `obligation = 0` → insert run `skipped_zero` / `paid` with zeros; return.  
7. `paid = min(coins, obligation)`; call `apply_club_economy(club, -paid, 0, 'weekly_payroll', 'weekly_payroll:'||club||':'||week, meta)`.  
8. Apply payment: reduce debt first, then bill; set `debt_after`, `strikes_after` ( +1 if `debt_after > 0` else 0 ).  
9. Insert `payroll_runs`; update `players.payroll_*`, `last_payroll_at`.  

## Errors

- Insufficient path is **not** an exception — partial pay is success.  
- Economy pipe still rejects negative resulting coins (should not happen if `paid ≤ coins`).  
- Missing player → exception / skip.

## Scheduler

- Bot job Monday 00:05 UTC → `rpc process_weekly_payroll`.  
- Retries safe due to unique `(club_id, week_key)`.

## Bot consumers

- `scheduler_jobs` / `weekly_payroll_job`  
- Finances embed reads latest `payroll_runs` + `players.payroll_debt/strikes`  
- Smoke: `scratch/smoke_weekly_payroll.py`

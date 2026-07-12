# Contract: `backfill_injury_eta_fairness` RPC

**Migration**: `057_hospital_eta_backfill.sql`  
**Signature**: `public.backfill_injury_eta_fairness() RETURNS JSONB`  
**Security**: `SECURITY DEFINER`, `search_path = public`  
**Grants**: `anon, authenticated, service_role` (ops via service / DATABASE_URL)

## Behavior

### Hospital branch (active patients)

For each `hospital_patients` row with `discharge_date IS NULL`, join `players` for `hospital_level` and `player_cards` (skip missing/retired):

1. `base := CASE tier WHEN 1 THEN 1 WHEN 2 THEN 4 ELSE 7 END`
2. `new_total := CEIL(base::numeric / (1 + 0.2 * hospital_level))`
3. `candidate := admission_date + (new_total || ' days')::interval`
4. `final_eta := LEAST(expected_recovery_date, candidate)`
5. If `NOW() >= final_eta` → **early recovery**:
   - `discharge_date = NOW()`
   - Clear card injury fields; `in_hospital = FALSE`; `fatigue = LEAST(100, fatigue + 25)`
   - Append to `early_discharged` result array
6. Else if `final_eta < expected_recovery_date`:
   - `UPDATE expected_recovery_date = final_eta`
   - Sync `player_cards.injury_recovery_days` to remaining whole days until `final_eta` (at least 1 while still injured)
7. Else: count unchanged

### Overflow branch

Cards with `injury_tier IS NOT NULL AND in_hospital = FALSE AND NOT retired`, no active hospital row required:

1. `elapsed_days := EXTRACT(EPOCH FROM (NOW() - COALESCE(injury_started_at, NOW()))) / 86400.0`  
   (null start → elapsed 0 via `COALESCE(injury_started_at, NOW())` ⇒ elapsed 0)
2. `remain := GREATEST(0, CEIL(base - elapsed_days))`
3. `final_days := LEAST(injury_recovery_days, remain)`
4. If `final_days = 0` → clear injury fields  
5. Else if `final_days < injury_recovery_days` → update days  
6. Else unchanged

### Return JSON

See `data-model.md`. Always return counts + `early_discharged` array (may be empty).

## Idempotency

Second invocation: hospital candidates unchanged → LEAST no-op; overflow already at min → no-op; no duplicate discharge of already `discharge_date IS NOT NULL` rows.

## Non-goals

- No Discord calls  
- No fatigue/coin changes except the +25 on hospital recovery clear  
- No rewrite of historical discharged rows

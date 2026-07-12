# Contract: process_stat_drill soft-reset parity

**Migration**: `058_daily_drill_cap_desync.sql`  
**Function**: `public.process_stat_drill(bigint, uuid, text)`

## Change

Replace:

```sql
IF v_reset < CURRENT_DATE THEN
```

With:

```sql
IF v_reset IS NULL OR v_reset < CURRENT_DATE THEN
    v_daily := 0;
    v_reset := CURRENT_DATE;
END IF;
```

Rest of function body stays as current live version (043 + later facility/age behavior). Prefer copy latest `process_stat_drill` from `043_club_facilities.sql` and patch only the soft-reset lines (and any injury guards already present).

## Recovery

`process_recovery_session` already null-safe in `055` — verify; only REPLACE if drift found.

## Guard

Ensure function still registered; no new table guards required unless repair RPC is added to verify list.

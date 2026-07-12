# Contract: injury base days 1 / 4 / 7

**RPCs** (replace bodies from migration `050`):

- `public.process_post_match_injuries(bigint, jsonb)`
- `public.admit_to_hospital(bigint, uuid)`

## Required change

Replace:

```sql
v_base_days := CASE v_tier WHEN 1 THEN 3 WHEN 2 THEN 8 ELSE 20 END;
```

With:

```sql
v_base_days := CASE v_tier WHEN 1 THEN 1 WHEN 2 THEN 4 ELSE 7 END;
```

Hospital shortening **unchanged**:

```sql
v_recovery_days := CEIL(v_base_days::NUMERIC / (1 + 0.2 * v_hospital))::INTEGER;
-- then GREATEST(1, …) if present in admit path
```

## Behavior

| Event | Uses new bases? |
|-------|-----------------|
| Auto-admit on post-match injury | Yes |
| Manual `admit_to_hospital` | Yes |
| Overflow admit later | Yes (same functions) |
| Open `hospital_patients` rows | **No** rewrite |

## Python mirror

`packages/player_engine/player_engine/injury_math.py`:

```python
BASE_RECOVERY_DAYS = {1: 1, 2: 4, 3: 7}
```

`recovery_days_for_tier` formula unchanged (`ceil(base / (1 + 0.2 * H))`, min 1).

## Out of scope

- Injury chance / A+C soft-cap
- Hospital bed capacity / upgrade costs
- Discharge / daily day-decrement logic

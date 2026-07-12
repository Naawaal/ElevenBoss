# Contract: TG-scaled `process_daily_recovery`

**Feature**: `009-fatigue-recovery`  
**Migration**: `054_fatigue_recovery.sql` (planned)  
**Caller**: `apps/discord_bot/core/scheduler_jobs.py` → `daily_recovery_job` (unchanged schedule: cron 00:05)

## Signature

```sql
process_daily_recovery() RETURNS JSONB
```

Unchanged signature; body replaced.

## Fatigue portion (changed)

For each non-retired card with `fatigue < 100`:

```text
IF in_hospital THEN
  bump = get_game_config_int('fatigue_hospital_per_day', 45)
ELSE
  bump = get_game_config_int('fatigue_passive_base', 15)
        + COALESCE(owner.training_ground_level, 1)
          * get_game_config_int('fatigue_passive_tg_per_level', 5)
END IF
fatigue = LEAST(100, fatigue + bump)
```

Implement via `UPDATE player_cards … FROM players` join on `owner_id = discord_id` (no per-row app loop).

## Unchanged portions

- Hospital discharge when `expected_recovery_date <= NOW()`
- Untreated injury day decrement / clear
- Discharge fatigue bump (+25) for just-discharged patients (existing 050 behavior)

## Return JSON

Keep existing keys; optional add `passive_mode: 'tg_scaled'` for ops visibility — not required by bot.

```json
{
  "fatigue_updated": 123,
  "discharged": 2,
  "untreated_decremented": 5
}
```

## Pure mirror

`player_engine.fatigue.passive_recovery_amount(tg_level: int) -> int`  
`apply_passive_recovery(current, *, in_hospital=False, tg_level=1) -> int`

Tests update `tests/test_fatigue_injury_math.py` for TG 1→20, TG 5→40, hospital unchanged.

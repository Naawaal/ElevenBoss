# Contract: game_config fatigue retune

**Migration**: `056_recovery_qol_balance.sql`  
**Table**: `public.game_config`

## Upsert (must `ON CONFLICT DO UPDATE`)

```sql
INSERT INTO public.game_config (key, value_json) VALUES
  ('fatigue_passive_base', '25'),
  ('fatigue_bench_per_match', '25'),
  ('fatigue_base_drain', '18')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;
```

Do **not** use `DO NOTHING` — keys already exist from `050`/`054`.

## Unchanged keys

- `fatigue_passive_tg_per_level` = `5`
- `fatigue_hospital_per_day` = `45`
- `fatigue_recovery_session` = `40`
- `fatigue_recovery_energy` = `5`

## Runtime effects

| Key | Effect without bot deploy |
|-----|---------------------------|
| `fatigue_passive_base` | Next `process_daily_recovery` uses +25 base |
| `fatigue_bench_per_match` | Next `apply_match_fatigue` bench bump +25 |
| `fatigue_base_drain` | Docs/ops only until bot ships Python `FATIGUE_BASE_DRAIN=18` |

## Guard

Fail migration if any of the three values ≠ expected after upsert.

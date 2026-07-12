# Quickstart: Recovery QoL Balance

## Prerequisites

- Feature branch `011-recovery-qol-balance`
- Spec + plan approved; `DATABASE_URL` for apply scripts
- Migrations `050`–`055` already applied in target DB

## Apply

```powershell
python scratch/apply_migration_056.py
python scratch/verify_schema_full.py
# or: psql $env:DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

## Verify config live

```sql
SELECT key, value FROM game_config
WHERE key IN (
  'fatigue_passive_base',
  'fatigue_bench_per_match',
  'fatigue_base_drain',
  'fatigue_passive_tg_per_level'
)
ORDER BY key;
-- expect: 25, 25, 18, 5
```

## Unit tests

```powershell
pytest tests/test_fatigue_injury_math.py -q
```

Expect:

- Drain PHY70 / attack / intensity → **21**
- Passive TG1/3/5 → **30 / 40 / 50**
- Bench default → **+25**
- Minor untreated days → **1**; Moderate @ H3 → **3**

## Smoke (optional, staging)

1. Competitive match with a bench unused starter → fatigue **+25** (cap 100).
2. Daily recovery tick (or wait for scheduler) at TG3 → non-hospital card **+40**.
3. Force/admit a Major injury with Hospital L0 → expected window **~7 days**.
4. Confirm a card already mid-injury under old ETA is **unchanged**.

## Deploy order

1. Apply `056` on production DB  
2. Deploy bot with updated `player_engine` constants (drain must ship with bot)  
3. Ship `change_log.md` note

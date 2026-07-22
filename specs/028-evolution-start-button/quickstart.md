# Quickstart: Evolution Start Button Fix

## Prerequisites

- Feature dir: `specs/028-evolution-start-button`
- `DATABASE_URL` for migration apply
- Bot process that can reopen `/development` → Evolutions after deploy

## Apply

```powershell
python scratch/apply_migration_073.py
# or: psql $env:DATABASE_URL -f supabase/migrations/073_evolution_hub_status_config.sql

python scratch/verify_schema_full.py
# or: psql $env:DATABASE_URL -f supabase/scripts/verify_required_schema.sql

pytest tests/test_evolution_gate.py tests/test_evolution_hub_copy.py -q
```

## SQL sanity (cooldown source)

After apply, hub remaining for a club that started ~37 minutes ago should be ~**5h 23m** (6h config), not ~**9h 23m** (legacy 10h).

```sql
SELECT key, value
FROM game_config
WHERE key IN (
  'evolution_cooldown_hours',
  'evolution_max_active',
  'evolution_start_energy',
  'evolution_start_flat',
  'evolution_start_ovr_mult'
);

-- Replace discord_id with the club under test
SELECT public.get_evolution_hub_status(976054227459776582);
```

Check JSON: `cooldown_remaining_seconds` consistent with `evolution_cooldown_hours`; `start_coin_flat` / `start_coin_ovr_mult` (or mult) are 500 / 5, not multiplier 10.

## Manual Discord check

1. Open `/development` → Evolutions.
2. **During** real cooldown, free slots: Start disabled; Cooldown shows remaining **≤ 6h** window (not a 10h leftover after 6h elapsed).
3. **After** live cooldown with `0/3` (or free slot): Start enabled; Cooldown says ready (or replacement copy if applicable).
4. Resources line shows `500+5×OVR` (or equivalent), not `10×OVR`.

## Contracts

- [get-evolution-hub-status.md](./contracts/get-evolution-hub-status.md)
- [evolution-hub-start-cost-copy.md](./contracts/evolution-hub-start-cost-copy.md)

# Quickstart: Hospital ETA Backfill

## Prerequisites

- Feature branch `012-hospital-eta-backfill`
- Migration **056** (011 bases) already applied
- `DATABASE_URL` in `.env`
- Optional for DMs: Discord bot token / running bot context

## Apply data pass

```powershell
python scratch/apply_migration_057.py
```

This creates/replaces `backfill_injury_eta_fairness` and **invokes it once**, printing the JSON summary.

Re-run safely:

```sql
SELECT public.backfill_injury_eta_fairness();
```

## Verify

```sql
-- Active stays should not outrun admission + new_total for their tier/H
SELECT hp.player_card_id, hp.injury_tier, p.hospital_level,
       hp.admission_date, hp.expected_recovery_date
FROM hospital_patients hp
JOIN players p ON p.discord_id = hp.owner_id
WHERE hp.discharge_date IS NULL;
```

```powershell
pytest tests/test_injury_eta_backfill.py -q
```

## Optional DMs

```powershell
python scratch/notify_hospital_eta_backfill.py
# or pass the early_discharged list from the last RPC result
```

Managers without DMs still see correct state under `/profile` → Manage Hospital.

## Deploy order

1. Confirm 056 live  
2. Apply 057 + run backfill  
3. Optional notify script  
4. Deploy bot only if notifier is wired into bot startup (prefer scratch one-shot; do not add a slash command)

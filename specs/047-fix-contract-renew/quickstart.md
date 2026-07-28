# Quickstart: Fix Contract Renew (`047`)

## Prerequisites

- Access to `DATABASE_URL`
- Bot can be restarted after migration + `player_cog` change

## 1. Apply migration

```powershell
python scratch/apply_migration_087.py
python scratch/verify_schema_full.py
# or: psql $env:DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

Confirm `renew_contract` accepts optional 5th arg / default key behaviour.

## 2. Unit / smoke checks

```powershell
pytest tests/test_contract_renew_fix.py -q
```

Expect: any pure helpers / documented assertions green.

## 3. SQL smoke (stuck card)

Using Roy Thompson (or another stuck card with old `contract_renewal:{uuid}` ledger row):

```sql
-- before
SELECT name, contract_expires_at FROM player_cards WHERE id = '854ec9e5-b09a-4941-8341-7c9cc0d2bb7c';

SELECT public.renew_contract(
  840864839240253440,
  '854ec9e5-b09a-4941-8341-7c9cc0d2bb7c',
  722,  -- or live calculated cost
  7,
  'manual-smoke-' || gen_random_uuid()::text
);

-- after: contract_expires_at should be ~ now()+7 days
SELECT name, contract_expires_at FROM player_cards WHERE id = '854ec9e5-b09a-4941-8341-7c9cc0d2bb7c';
```

Second call with the **same** 5th key within replay semantics must not double-charge.

## 4. Discord smoke

1. Restart bot with updated `player_cog`.
2. Crimson FC (or affected club): `/player-profile` → Roy Thompson (or stuck card).
3. Renew → success shows new expiry; match/squad no longer lists that card as past grace.
4. Double-tap quickly → at most one charge.

## 5. Ops note (emergency)

Prefer player renew after deploy. If you must unblock before bot ship: call fixed `renew_contract` once with a unique `p_idempotency_key` (charges coins). **Do not** delete `economy_ledger` rows as the default fix.

## 6. Changelog

Add a short `change_log.md` note: contract renew works again after the first renewal; re-open `/player-profile` and renew if you were stuck.

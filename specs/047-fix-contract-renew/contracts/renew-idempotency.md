# Contract: `renew_contract` Idempotency

**Feature**: `047-fix-contract-renew`  
**Migration**: `087_fix_contract_renew_idempotency.sql`  
**Consumers**: `apps/discord_bot/cogs/player_cog.py` renew button; any future callers of `renew_contract`

## Signature

```text
renew_contract(
  p_club_id BIGINT,
  p_card_id UUID,
  p_cost BIGINT,
  p_extension_days INTEGER,
  p_idempotency_key TEXT DEFAULT NULL
) RETURNS BOOLEAN
```

Drop prior 4-arg overload so only one signature remains.

## Idempotency key

```text
effective_key := COALESCE(
  NULLIF(btrim(p_idempotency_key), ''),
  'contract_renewal:' || p_card_id::text || ':' ||
    to_char(date_trunc('minute', timezone('utc', now())), 'YYYYMMDDHH24MI')
)
```

| Rule | Requirement |
|------|-------------|
| Forbidden | Permanent `contract_renewal:{card_id}` alone as the only key forever |
| Pass to | `apply_club_economy(..., source := 'contract_renewal', idempotency_key := effective_key, ...)` |
| Fresh debit | Extend `contract_expires_at` (from `now()` if null/expired, else from current expiry) by `p_extension_days` |
| Replay | Do **not** apply a second debit; do **not** extend again; may return `TRUE` |

## Unchanged guards

- Card owned by `p_club_id`, not retired
- Age ≥ `retirement_warning_age` → `RAISE`
- Coins only via `apply_club_economy` (no direct `players.coins` UPDATE)

## Grants / verify

- `GRANT EXECUTE` to `anon, authenticated, service_role` (match prior)
- Update `verify_required_schema.sql` function probe to the new signature if it hard-codes arity

## Non-goals

- Changing cost formula or grace days
- Deleting historical ledger rows

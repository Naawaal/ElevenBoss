# Contract: Role Persistence RPCs

## Problem

`player_cards.role` exists and UI reads it, but intake RPCs never INSERT it — every new card becomes `Balanced`. Archetypes would be lost at the DB boundary without a forward migration.

## Migration

`supabase/migrations/051_card_role_persistence.sql` (name may vary; next free number if 051 taken).

### Schema

```sql
ALTER TABLE public.scouting_pool_players
  ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'Balanced';
```

`player_cards.role` already present (migration 003) — do not recreate.

### RPC body updates (signatures unchanged)

For each jsonb card ingest path, extend `jsonb_to_recordset` / jsonb reads with `role TEXT` and INSERT `COALESCE(role, 'Balanced')`:

| Function | Notes |
|----------|-------|
| `register_new_player` | Starter squad cards |
| `claim_daily_pack` | Daily pack |
| `process_youth_intake` | Academy intake |
| `insert_scouting_pool_player` | Persist pool `role` from `p_card` |
| `purchase_scouting_player` | Copy pool `role` into `player_cards` |

### Bot payload

`apps/discord_bot/core/card_payload.py` → `card_rpc_payload` and `scouting_pool_payload` MUST include `role`.

## Guarantees

- New cards from all factory-backed intake paths store the archetype name in `role`.
- Missing/null `role` in payload still inserts safely as `Balanced` (backward compatible clients).
- No new slash commands; no RLS policy inventiveness beyond existing table patterns.

## Verify

Extend `supabase/scripts/verify_required_schema.sql` with `column:public.scouting_pool_players.role` (and `player_cards.role` if not already listed). Apply via `scratch/apply_migration_051.py` before shipping bot changes that depend on persisted role.

## Non-goals

- Backfill UPDATE of historical `Balanced` rows
- New archetype table or enum constraint (plain TEXT is enough for v1; catalog enforced in Python)

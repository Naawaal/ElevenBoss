# Quickstart: Identity & Ownership (US-42.1)

## Prerequisites

- Read [spec.md](./spec.md) US1–US3 and [plan.md](./plan.md) waves
- `DATABASE_URL` for migration apply (optional until W1)
- Repo with Speckit feature `specs/030-identity-ownership`

## Validation 0 — Comprehension

Answer without cogs:

1. Can one Discord user own two clubs?  
2. Does leaving a guild delete the club?  
3. Who gets pending level rewards after a transfer?  
4. What happens on concurrent double register?

**Expect**: No; No; current owner; ≤1 club / already-registered.

## Validation 1 — W0 audit greps

```bash
rg -n "ALREADY_REGISTERED|register_new_player" supabase/migrations apps/discord_bot
rg -n "on_guild_remove|pause_seasons_for_guild|players\".delete|DELETE FROM players" apps/discord_bot
rg -n "claim_pending_level_rewards|owner_id" supabase/migrations/025_player_level_system.sql
```

**Pass**: Register raises already-registered; guild remove → pause only; claim filters `owner_id`.

## Validation 2 — Apply 074 (after implement)

```bash
python scratch/apply_migration_074.py
# or project-standard apply
psql "$DATABASE_URL" -f supabase/scripts/verify_required_schema.sql
```

**Pass**: New columns exist; guards for new RPCs pass.

## Validation 3 — Tests

```bash
pytest tests/test_register_idempotency.py tests/test_identity_lifecycle.py -q
pytest tests/test_pending_rewards_current_owner.py -q
```

**Pass**: SC-001 class + lifecycle classify math + current-owner claim.

## Validation 4 — Persona smoke (manual)

1. Register on guild A → club created.  
2. Leave A / remove bot → club row still present; season paused if any.  
3. Re-add bot / join B → same club; `/register` says already registered.  
4. Double-tap Confirm in a fresh wizard while already registered → friendly already-registered.

## Out of scope here

- Full US-42.3 abandonment automation productization  
- Marketplace race tests (separate)  
- Economy pipe changes  

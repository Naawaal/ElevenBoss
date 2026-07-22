# Contract: Register Idempotency

**Feature**: US-42.1 | **Parent INV**: INV-01, INV-08

## Goal

At most one human club per Discord id under double-click, retry, and concurrent confirm.

## Current behavior

- UI pre-check on `/register`
- RPC `register_new_player` raises `ALREADY_REGISTERED` if row exists
- PK on `players.discord_id`

## Required behavior (074)

1. Pre-check EXISTS → `ALREADY_REGISTERED` (keep).
2. On concurrent insert collision (`unique_violation`), raise **`ALREADY_REGISTERED`** (same message family) — not a generic error.
3. Transaction remains atomic: failure after partial inserts must roll back (plpgsql function default).
4. Whitespace-only names still rejected.
5. `is_ai` must be false for human register inserts.
6. New columns: set `identity_status = 'active'`, `last_qualifying_activity_at = NOW()`.

## App mapping

`onboarding_cog.py` continues to map `ALREADY_REGISTERED` substring to friendly copy; extend if unique_violation text differs before 074.

## Tests

| Case | Expect |
|------|--------|
| Second register same id | `ALREADY_REGISTERED`, one row |
| Parallel two confirms | one row; loser already-registered |
| Abort pre-RPC | zero rows |

## Non-goals

- Changing starter squad contents or opening balances (US-01 product).

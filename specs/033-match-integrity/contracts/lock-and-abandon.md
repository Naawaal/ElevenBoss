# Contract: Lock & Abandon

**Feature**: US-42.4 | INV-17 | Migration `077`

## Acquire

- Bot: acting club before sim
- Friendly: both clubs
- League human play **and** lifecycle deadline sim: **both** human clubs

## Release

- `finally` on happy/error paths **and** terminal RPCs must clear locks
- Prefer `abandon_match_run` / `complete_run` + explicit release over blind table wipe

## `abandon_match_run(p_run_id)`

1. Lock run row `FOR UPDATE`
2. If already `completed` → no-op success (do not delete rewards)
3. If `abandoned`/`failed` → ensure locks cleared; return
4. Else set `abandoned` (or `failed`), `completed_at=NOW()`
5. `release_match_lock` for home, away, active (humans only / all present ids)

## `reconcile_orphaned_match_locks()`

Delete `match_locks` rows whose `discord_id` has **no** `match_runs` in (`streaming`,`completing`) referencing them as home/away/active.

## Boot recovery

1. Interrupted runs: complete-if-rewarded else `abandon_match_run`
2. Then `reconcile_orphaned_match_locks` (not unconditional wipe of all locks)

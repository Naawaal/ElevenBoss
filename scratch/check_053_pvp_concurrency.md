# Scratch note: PvP double-pair concurrency (T019)

Manual / SQL harness (clone DB, `battle_pvp_enabled=true`):

1. Insert two `searching` queue rows same `guild_id`.
2. From two sessions: `SELECT try_match_pvp_queue(<guild>);` concurrently.
3. Expect: exactly one `match_runs` row with `run_type='pvp'`; both queue rows `matched` to that run OR one matched and the other still searching / no second run.

Automated dual-session lock stress can be added later; SKIP LOCKED + sorted dual locks are the invariant.

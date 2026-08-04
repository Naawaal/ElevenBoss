# Scratch: finalize_pvp_match idempotency (T034)

With `pvp_rewards_enabled=true` on a clone:

1. Complete one PvP run to `streaming`/`completing` with known scores.
2. `SELECT finalize_pvp_match('<run>', h, a, r1, r2);` twice.
3. Expect: second call returns `already` / prior payload; **one** pair of economy ledger rows per manager; LP applied once; two `match_history` rows total for the run.

# Contract: Match Path Audit (W0)

**Feature**: US-42.4 | Filled from implement research 2026-07-22

## Critical (must fix in 077 / cog patches)

| Gap | Location | Fix |
|-----|----------|-----|
| Present failure → `abandon_run` after rewards | `battle_cog` bot finalize except | Present-retry only; `complete_run` if paid |
| Rewards before durable complete_run pairing | bot/league reward helpers vs `complete_run` | Order: pay → complete_run → present |
| League play locks one club only | `execute_league_match` | Lock both humans |
| League fail unlocks, run may stay streaming | `execute_league_match` finally | `abandon_match_run` on hard fail |
| Boot always abandons bot mid-stream | `match_recovery` | Complete-if-rewarded else abandon RPC |
| Blind wipe all `match_locks` at boot | `match_recovery` | `reconcile_orphaned_match_locks` |

## Soft

| Gap | Notes |
|-----|-------|
| Career stats not keyed by run | Defer unless cheap |
| League recovery early-return soft-stall | Harden with abandon/reconcile |
| No periodic sweeper | Optional APScheduler; boot reconcile required |

## Already OK

- Economy key `match:{run_id}:{club_id}`
- XP/`xp_applied_at` + evo tick only in `process_match_result`
- Friendly sandbox (no tick/economy/XP)
- Fixture unique active run index

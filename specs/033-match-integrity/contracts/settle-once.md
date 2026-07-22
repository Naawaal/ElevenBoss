# Contract: Settle Once

**Feature**: US-42.4 | INV-09, INV-10

## Economy

- Key: `match:{match_run_id}:{club_id}` via `apply_match_economy` / `apply_club_economy`
- Replay → prior ledger row / no-op credit

## XP / evolution

- Bot/league: `process_match_result` with history id; `xp_applied_at` short-circuit
- `tick_evolution_match_progress` **only** inside that RPC
- Friendly: **forbidden** to call `process_match_result` / economy faucet

## Presentation

- After durable rewards + `complete_run`, Discord failures retry embed/thread only
- Must not re-enter reward functions solely because present failed

## Tests

- Double `apply_match_economy` same key → one effect
- Grep: zero `tick_evolution_match_progress` under `apps/`
- Friendly path: no economy/XP RPC

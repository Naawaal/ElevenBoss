# Contract: PvP finalize

**Feature**: `053-pvp-matchmaking-rivalries`  
**RPC**: `finalize_pvp_match(p_run_id, …server-owned result fields…)`

## Preconditions

- Lock run row; `run_type = 'pvp'`
- Status allows finalize (`streaming`/`completing`); idempotent if already `completed`
- Scores / seed / snapshot must match server run (reject client-escalated types and client LP)

## Atomic steps (single transaction)

1. Lock both manager rows (sorted IDs)
2. Charge both PvP energy via economy pipe
3. Apply both coin rewards (config multipliers × division bot baselines or explicit pvp keys)
4. Apply both XP via existing match XP path (`match_type` appropriate for XP multipliers — use dedicated `pvp` if progression supports it, else documented mapping; **never** client XP amounts)
5. Fatigue + injuries both sides
6. Update competitive career / PvP W-D-L (not Practice path)
7. Compute LP (opponent LP, result, relative rating, division, provisional protection); apply both
8. Insert two `match_history` rows (`match_type='pvp'`, `global_lp_delta`, `opponent_owner_id`, `rivalry_counted`)
9. If rivalries flag on: upsert `manager_rivalries` once; detect events; maybe append `pvp_badge_keys`
10. Mark run `completed`; release both locks
11. Return two-sided payload: coins, XP summary, LP deltas, rivalry events

## Guards

- Duplicate finalize → return prior payload, no second economy
- `pvp_rewards_enabled=false` → still may complete match for soak but skip coin/LP per flag policy (document: Stage 2 rewards off = complete run, zero economy/LP)
- Abandoned pre-kickoff never calls finalize with rewards

## Bot responsibility after RPC

Present full-time embeds (both managers), rivalry callouts if prefs allow, rate-limited rivalry DMs (slice 2). Simulation already finished before finalize.

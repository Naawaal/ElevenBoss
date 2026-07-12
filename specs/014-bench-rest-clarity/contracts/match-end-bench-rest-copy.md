# Contract: Match-end bench rest copy

**Feature**: `014-bench-rest-clarity`

## When

After a **bot** or **league** match completes fitness successfully.

## Copy (keep short)

Prefer one of:

- `Bench rest: +25 fitness for {n} reserves (cap 100).`
- `Bench rest: reserves already fresh (100).` when `n_rested == 0` or all candidates were already at cap (if detectable from RPC/client pre-check; otherwise omit second line).

On fitness **failure**:

- Ephemeral or result footer: `Fitness update failed — rewards still counted. Try again later or contact support if fatigue looks stuck.`

## Surfaces

- Bot: match result finalize embed / follow-up already used by `battle_cog`
- League: equivalent post-match human summary if one exists; else ephemeral to manager

## Non-goals

- No new slash command
- No DM spam for routine success

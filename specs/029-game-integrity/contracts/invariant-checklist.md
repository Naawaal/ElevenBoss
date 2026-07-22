# Contract: Invariant Checklist (US-42 Review Gate)

**Parent**: [spec.md](../spec.md)  
**Use**: Every PR / Speckit plan that mutates ownership, rewards, competitive state, or durable inventory MUST pass this checklist before merge/enablement.

## How to use

1. Author cites **US-42** + child ID (US-42.x) in the plan or PR description.
2. Reviewer marks each applicable INV. Mark N/A only with a one-line reason.
3. Any FAIL blocks merge unless an epic amendment is approved first.

## Checklist

| ID | Invariant | Pass? | Evidence (RPC / test / spec cite) |
|----|-----------|-------|-----------------------------------|
| INV-01 | ≤1 club per Discord user | ☐ | |
| INV-02 | Card has exactly one current owner | ☐ | |
| INV-03 | No illegal exclusive-state overlap | ☐ | |
| INV-04 | Coins never negative; failed debit no side effects | ☐ | |
| INV-05 | Coins/energy only via economy pipeline + ledger | ☐ | |
| INV-06 | XP/level only via XP pipeline | ☐ | |
| INV-07 | SP available = earned − spent (≥0) | ☐ | |
| INV-08 | Reward ≤ once per idempotency key | ☐ | |
| INV-09 | Settlement before/with rewards atomically | ☐ | |
| INV-10 | Evolution match tick ≤ once per card per match | ☐ | |
| INV-11 | Friendly is sandbox (no competitive coin/XP faucet) | ☐ | |
| INV-12 | ≤1 active guild-league seat per season rules | ☐ | |
| INV-13 | Concurrent buy → one winner; loser unchanged | ☐ | |
| INV-14 | Pending level rewards → current owner | ☐ | |
| INV-15 | AI clubs: no human-only prizes / no human debt via AI payroll | ☐ | |
| INV-16 | Schema guards cover new required objects | ☐ | |
| INV-17 | Match-lock blocks roster/dev/sale mutations | ☐ | |
| INV-18 | Caps enforced server-side in mutation path | ☐ | |

## Additional gates (non-INV but required)

| Gate | Pass? | Notes |
|------|-------|-------|
| Discord UI is presentation-only (server revalidates) | ☐ | |
| Failure copy is user-safe (no raw traceback) | ☐ | |
| New faucet/sink registered (US-42.7) if applicable | ☐ | |
| Job catch-up safe if scheduler-touched | ☐ | |
| No new slash/hub/table beyond child Locked scope | ☐ | |
| `change_log.md` if manager-visible integrity change | ☐ | |

## Replay / double-invoke (INV-08)

Before marking INV-08 Pass/N/A, check [idempotency-anchor-map.md](./idempotency-anchor-map.md) for the logical action’s key pattern and regression anchors. Epic `029` does not add pytest — children own remaining gaps listed there.

## Fail closed examples

- Top.gg down → pack claim denied (no free pack).
- Stale listing price → purchase rejected.
- Double login claim → second returns already claimed / prior result.

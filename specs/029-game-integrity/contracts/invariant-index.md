# Contract: Invariant Index (INV-01…INV-18)

**Parent**: [../spec.md](../spec.md) §2 — one-liners for PR citation. Full wording lives in the epic.

| ID | One-liner |
|----|-----------|
| INV-01 | ≤1 club per Discord user |
| INV-02 | Card has exactly one current owner |
| INV-03 | No illegal exclusive-state overlap |
| INV-04 | Coins never negative; failed debit no side effects |
| INV-05 | Coins/energy only via economy pipeline + ledger |
| INV-06 | XP/level only via XP pipeline |
| INV-07 | SP available = earned − spent (≥0) |
| INV-08 | Reward ≤ once per idempotency key |
| INV-09 | Settlement before/with rewards atomically |
| INV-10 | Evolution match tick ≤ once per card per match |
| INV-11 | Friendly is sandbox (no competitive coin/XP faucet) |
| INV-12 | ≤1 active guild-league seat per season rules |
| INV-13 | Concurrent buy → one winner; loser unchanged |
| INV-14 | Pending level rewards → current owner |
| INV-15 | AI clubs: no human-only prizes / no human debt via AI payroll |
| INV-16 | Schema guards cover new required objects |
| INV-17 | Match-lock blocks roster/dev/sale mutations |
| INV-18 | Caps enforced server-side in mutation path |

**Review gate**: [invariant-checklist.md](./invariant-checklist.md)

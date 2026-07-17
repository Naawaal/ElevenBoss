# Contract: Money & Award Idempotency

**Feature**: `022-v1-stability-blueprint`  
**Maps to**: Spec C1–C4, H4, H9, User Story 2, SC-001–SC-003

## Invariants (must remain true)

| Path | Invariant | Existing mechanism (verify / repair) |
|------|-----------|--------------------------------------|
| P2P purchase | ≤1 successful buyer; no double debit; no duplicate card owners | `purchase_transfer_listing` locking + ledger; `tests/test_transfer_market_race.py` |
| Stale price confirm | Reject when expected price ≠ live listing price | Purchase RPC expected-price guard |
| Listed / XI inconsistent | Cannot list or buy into illegal squad states | List/purchase peer guards; match gates |
| Weekly payroll | Same club+week billed at most once | `payroll_runs` unique + ledger key `weekly_payroll:{club}:{week}` |
| MoMD | ≤1 award per season+matchday; all-auto-sim MD ⇒ 0 | Awards uniqueness + ledger key; MoMD selection rules |
| League daily tick | Fixture resolved once; no admin Start race under automation | State machine ownership; admin Open/Start gated |
| Match coins | Bot/league via `apply_club_economy` + match run idempotency | `economy_rpc` / match rewards |
| Double-tap hubs | Second invoke is no-op or clear already-done | RPC uniqueness / daily logs (mentor, pack, drills) |

## Remediation policy

1. Prefer fixing the **shared RPC / unique constraint** over adding UI-only disables.
2. UI disables are UX sugar after the atomic guard exists.
3. New migration only if uniqueness or guard missing (Conditional Path in plan).

## Error copy (user-visible)

Race losers and stale confirms MUST receive short ephemeral reasons (“Already sold”, “Price changed”, “Already paid this week”) — never raw SQL / traceback.

## Exit evidence

- Critical IDs Closed with named test or smoke step
- Forced re-run of payroll / MoMD / purchase loser path documented in quickstart

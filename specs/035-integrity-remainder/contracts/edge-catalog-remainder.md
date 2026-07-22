# Contract: Edge Catalog Remainder (US-42.10)

**Status**: Complete for remainder Lock (2026-07-22). Covers epic §8 categories relevant to W6–W10.

| ID | Category | Scenario | Expected | Recovery |
|----|----------|----------|----------|----------|
| R-01 | Marketplace | Two buyers race | One win | RPC `FOR UPDATE` |
| R-02 | Marketplace | Buy own listing | Block | RPC raise |
| R-03 | Marketplace | Expiry twice | One expire | Status≠active |
| R-04 | Marketplace | List while MatchLocked / Hospital / Evolving | Block | `assert_card_action_allowed` |
| R-05 | Marketplace | Relist inside cooldown | Block | `transfer_relist_cooldown_hours` |
| R-06 | Economy | Direct coins UPDATE in apps | Forbidden | `test_economy_registry_guards` |
| R-07 | Economy | Replay same economy key | No second grant | Ledger short-circuit |
| R-08 | Economy | Top.gg down on vote claim | Fail closed | Store path |
| R-09 | Economy | Friendly complete | No coin faucet | INV-11 |
| R-10 | Economy | Missing registry entry for new faucet | Review fail | FR-E03 |
| R-11 | Jobs | Double scheduler wake | ≤1 mutation | Run key / RPC |
| R-12 | Jobs | Offline across payroll Monday | Catch-up once | Week key |
| R-13 | Jobs | Expiry after sold | No-op | Batch filter |
| R-14 | Jobs | Lifecycle wake twice same op | Second acquire fails | US-42.5 `_run_once` |
| R-15 | DB | Undeclared column in bot | Fail review | W9 checklist |
| R-16 | DB | Table no RLS on Data API | Forbidden | Migration policy |
| R-17 | DB | Drop RPC without DROP old overload | Ambiguous signature | Checklist |
| R-18 | UX | Stale market buy button | Reject / unavailable | Owner + status |
| R-19 | UX | Empty select | No-op | Existing patterns |
| R-20 | UX | Interaction timeout | Defer first | Constitution IV |
| R-21 | Identity | Leave guild mid-list | Club persists | US-42.1 |
| R-22 | Transfer fairness | Claim pending after P2P buy | Current owner | INV-14 |
| R-23 | External | Webhook replay | Idempotent | Consume key |
| R-24 | Scheduler | Clock skew across hosts | UTC job intents | Catalog |
| R-25 | Capacity | Max active listings | Block new list | `017` caps |
| R-26 | Analytics | Monitoring down | Grants still work | Signals Soft |
| R-27 | League×Market | List during paused season | Allowed if card free | Season≠card busy |
| R-28 | Match×Market | List during MatchLocked | Block | INV-17 |

Epic §8 index coverage: identity, registration, match (cite 42.4), friendly, marketplace, economy, scheduler, Discord UX, external deps, host restart, flags, AI (cite 42.5 prizes), capacity, permissions, multi-session, clock, analytics — each has ≥1 remainder row or points at Locked child.

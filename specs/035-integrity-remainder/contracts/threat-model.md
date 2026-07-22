# Contract: Threat Model (US-42.10) — Soft

**Status**: Complete for remainder Lock (2026-07-22)

## Assets

Club coins/energy, card ownership, listings, match/league results, ledger integrity, Discord interaction authenticity, job run uniqueness.

## Actors

Honest manager · double-tap / multi-device · racing buyers · stale-view attacker · alt flip farmer · webhook replay · ops with DB access (trusted).

## In-scope soft controls

| Control | Where |
|---------|--------|
| Price floors / min hold / listing caps | `017` + transfer RPCs |
| Own-buy block + listing FOR UPDATE | `purchase_transfer_listing` |
| Card busy + MatchLocked | US-42.2 `assert_card_action_allowed` |
| Economy idempotency keys | Registry W7 |
| Job / lifecycle run keys | Catalog W8 / US-42.5 |
| Fail-closed Top.gg / external | Store vote paths |
| Stale custom_id / owner checks | Hub views |

## Out of scope

Accusation-based bans, KYC, legal takedowns, multi-club product, hard IP bans.

## Priority abuses → mitigation

| Abuse | Mitigation |
|-------|------------|
| Double buy listing | W6 RPC lock |
| Parallel coin writer | W7 registry + greps |
| Duplicate job pay | W8 run keys |
| Half migration | W9 checklist / INV-16 |
| Stale button grant | Owner checks + re-open guidance |
| Friendly farm | INV-11 / registry n/a row |

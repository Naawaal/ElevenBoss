# Contract: Remainder Audit (W0)

**Feature**: US-42.6–42.10 | 2026-07-22

## Critical (must deliver)

| Gap | Domain | Fix |
|-----|--------|-----|
| No living faucet/sink registry | W7 | Author `economy-source-sink-registry.md` + grep guards |
| No job catalog | W8 | Author `job-catalog.md` from `main.py` jobs |
| No RPC guarantee checklist artifact | W9 | Author `rpc-guarantee-checklist.md` |
| No remainder threat/edge catalog | W10 | Author threat + edge docs |

## Soft

| Gap | Notes |
|-----|-------|
| Transfer tax no separate ledger sink row | Document implicit burn; optional 078 |
| Expiry job no per-listing run key | Batch UPDATE idempotent |
| Gems (`tokens`) not in economy pipe | Registry N/A until product defines mutations |
| Buyer-side purchase vs full card matrix | Seller list gated; buyer is club coins — Soft |

## Already OK

- `purchase_transfer_listing` FOR UPDATE + own-buy block + dual economy keys
- List path `assert_card_action_allowed(..., list_transfer)` + match lock (`075`)
- Listing statuses active/sold/cancelled/expired
- App layer: no direct `players.coins` updates found
- League ops `_run_once` (US-42.5); match settle-once (US-42.4)
- Friendly sandbox (US-42.4 tests)

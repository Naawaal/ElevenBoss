# Contract: Marketplace Hot Path

**Feature**: `045-marketplace-ux-polish`

## Board fetch rules

| Interaction | DB `_board_listings`? |
|-------------|------------------------|
| Apply Filters / first results entry | **Yes** |
| Change Sort on current results | **No** — re-sort in memory via existing `sort_transfer_listings` |
| Select listing for detail | **No** — use `self.listings` |
| After successful buy / cancel list | **Yes** refresh (or return to hub) |
| Discovery / ownership on detail | Existing RPCs OK (not a full board re-fetch) |

## Eligibility queries

`active_training` (and similar lock checks) for Sell / List Player MUST be scoped to the viewing manager’s card ids (or equivalent owner filter) — **not** an unfiltered global table read.

## Column selection

Hub player row, sell/list roster, and scouting pool opens SHOULD request only columns needed for display/eligibility (avoid `select("*")` habit on those paths).

## Integrity

Purchase/list/agent/scout RPCs remain source of truth. In-memory board may be stale after races — RPC errors remain authoritative; show clear failure copy.
)

# Contract: Transfer History Enrichment

**Feature**: `043-marketplace-intelligence`  
**Extends**: `017` `purchase_transfer_listing` / `transfer_sales_log`

## Schema

ALTER `transfer_sales_log` add (all nullable for legacy rows):

- `fair_value_coins BIGINT`
- `rarity TEXT`
- `role TEXT`
- `overall INTEGER`
- `potential INTEGER`
- `age_at_sale INTEGER`
- `player_name TEXT`

Indexes per [data-model.md](../data-model.md).

## Purchase write (same transaction as today)

Inside `purchase_transfer_listing`, after locking the card and before/with sales log INSERT:

1. Read card attrs: name, role, overall, rarity, potential, effective age.  
2. `v_fair := compute_agent_offer(ovr, rarity, age, potential)`.  
3. INSERT `transfer_sales_log` including existing money columns **plus** snapshot columns (all non-null for new rows).

Failed purchases (any RAISE before commit) MUST NOT insert a sales log row (unchanged).

## Immutability

- No RPC updates sales log money/snapshot fields.  
- Relist cooldown continues to use `(buyer_id, card_id, created_at)`.

## Returns

Purchase JSON MAY add `fair_value_coins` for UI confirmation; not required for correctness.

## Errors

Unchanged purchase errors. Missing card attrs → RAISE (card unavailable) as today.

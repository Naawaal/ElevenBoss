# Contract: Purchase Transfer Listing

**Feature**: `017-player-transfer-market`  
**Economy**: All coin moves via `apply_club_economy`

## `purchase_transfer_listing(p_buyer_id bigint, p_listing_id uuid, p_expected_price bigint) → jsonb`

### Preconditions

1. Feature flag on.
2. `assert_not_in_match(p_buyer_id)`.
3. Lock listing `FOR UPDATE` where `id = p_listing_id AND status = 'active'`.
4. `expires_at > now()` (else treat as unavailable / run expire path).
5. `p_expected_price IS NOT DISTINCT FROM price_coins` (stale UI guard).
6. `p_buyer_id <> seller_id`.
7. Buyer coins ≥ `price_coins` (enforced inside `apply_club_economy`).
8. Buyer senior roster count (non-academy, non-retired `player_cards`) &lt; `senior_roster_cap`.
9. Card still owned by `seller_id` and not assigned to XI (defensive).

### Effects (single transaction)

1. `gross = price_coins`; `tax` / `net` per tax contract.
2. `apply_club_economy(buyer, -gross, 0, 'transfer_buy', 'transfer_buy:'||listing_id, meta)`.
3. `apply_club_economy(seller, +net, 0, 'transfer_sale', 'transfer_sale:'||listing_id, meta)`.
4. `UPDATE player_cards SET owner_id = buyer WHERE id = card_id AND owner_id = seller`.
5. Close listing: `status=sold`, `buyer_id`, `sold_at=now()`.
6. Insert `transfer_sales_log`.

### Race

- Second buyer: no active row under `FOR UPDATE` → raise `Listing not found or already sold`.
- Ledger idempotency keys ensure replay-safe double-invoke of same buyer does not double-pay (return replay / already completed carefully — prefer raise if listing already sold).

### Returns

```json
{
  "listing_id": "…",
  "card_id": "…",
  "player_name": "…",
  "gross_price": 2100,
  "tax_amount": 210,
  "seller_net": 1890,
  "seller_id": 123,
  "buyer_id": 456
}
```

### Errors

- `Transfer market is disabled`
- `Listing not found or already sold`
- `Price mismatch`
- `Cannot buy your own listing`
- `Insufficient coins`
- `Senior roster full`
- Match-lock messages from `assert_not_in_match`

### Peer guards (same migration or follow-up touch)

Update `process_agent_sale` (and any drill/fusion/evo/squad assign RPCs that lack it) to reject cards with an **active** transfer listing.

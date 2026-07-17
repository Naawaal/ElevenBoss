# Contract: Create / Cancel Transfer Listing

**Feature**: `017-player-transfer-market`  
**Flag**: RPCs raise if `NOT p2p_transfer_market_enabled()` (except cancel of already-active may still be allowed when flag flipped off mid-flight — **prefer allow cancel always** so cards do not strand)

---

## `create_transfer_listing(p_seller_id bigint, p_card_id uuid, p_price bigint) → jsonb`

### Preconditions

1. Feature flag on.
2. `assert_not_in_match(p_seller_id)`.
3. Card exists, `owner_id = p_seller_id`, not retired, not `in_academy`.
4. No injury / hospital (same spirit as agent sale cog).
5. Not in `squad_assignments`.
6. Not in active training / active evolution.
7. No other `transfer_listings` row with this `card_id` and `status = 'active'`.
8. Count of seller’s active listings &lt; `transfer_listing_slot_cap`.
9. Relist cooldown: no `transfer_sales_log` row for `(buyer_id = seller, card_id)` with `created_at` within cooldown hours.
10. `p_price` within floor/ceil for live card fair value.

### Effects

- Insert `transfer_listings` (`status=active`, `expires_at = now() + ttl`).
- Card remains in seller inventory; eligibility gates treat active listing as lock.

### Returns

```json
{
  "listing_id": "…",
  "card_id": "…",
  "price_coins": 2100,
  "seller_net_if_sold": 1890,
  "expires_at": "…",
  "active_listings": 2,
  "slot_cap": 5
}
```

### Errors (examples)

- `Transfer market is disabled`
- `Daily/slot listing limit` / `Listing slots full`
- `Cannot list …` (XI, evo, etc.)
- `Price must be between X and Y`
- `Card recently acquired via transfer; wait Nh`

---

## `cancel_transfer_listing(p_seller_id bigint, p_listing_id uuid) → jsonb`

### Preconditions

- Listing exists, `seller_id` matches, `status = 'active'`.

### Effects

- Set `status = cancelled`, `cancelled_at = now()`.
- Card immediately listable / usable again (no coin movement).

### Returns

```json
{ "listing_id": "…", "card_id": "…", "status": "cancelled" }
```

### Notes

- Allowed even if feature flag is false (unstick inventory after rollback).

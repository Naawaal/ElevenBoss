# Data Model: Player-to-Player Transfer Market

**Feature**: `017-player-transfer-market` | **Date**: 2026-07-14  
**Migration**: `062_p2p_transfer_market.sql`

## Entities

### TransferListing

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `seller_id` | BIGINT FK → `players.discord_id` | Listing owner |
| `card_id` | UUID FK → `player_cards.id` | ON DELETE CASCADE / restrict sale paths carefully |
| `price_coins` | BIGINT | Listed buy-it-now price (> 0) |
| `status` | TEXT | `active` \| `sold` \| `cancelled` \| `expired` |
| `created_at` | TIMESTAMPTZ | Default now() |
| `expires_at` | TIMESTAMPTZ | `created_at + ttl_hours` |
| `sold_at` | TIMESTAMPTZ NULL | Set on purchase |
| `buyer_id` | BIGINT NULL FK → `players` | Set on purchase |
| `cancelled_at` | TIMESTAMPTZ NULL | Cancel or expire |

**Relationships**

- One active listing per card (partial unique index).
- Seller may have many listings up to `transfer_listing_slot_cap`.

**Indexes**

- `UNIQUE (card_id) WHERE status = 'active'`
- `(status, expires_at)` for sweeper
- `(seller_id, status)` for My Listings
- Board browse: join `player_cards` on `card_id` filter `position`, `overall`, age (via DOB helper), `potential` where `status = 'active'`

### TransferSaleLog

Append-only completion record (audit + cooldown + ops tax metrics).

| Field | Type | Notes |
|-------|------|-------|
| `id` | BIGSERIAL / UUID PK | |
| `listing_id` | UUID FK → `transfer_listings` | |
| `seller_id` | BIGINT | |
| `buyer_id` | BIGINT | |
| `card_id` | UUID | Survives owner change |
| `gross_price` | BIGINT | Buyer paid |
| `tax_amount` | BIGINT | `gross - seller_net` |
| `seller_net` | BIGINT | Credited to seller |
| `created_at` | TIMESTAMPTZ | |

**Index**: `(buyer_id, card_id, created_at DESC)` for re-list cooldown.

### PlayerCard (existing — behavioral)

No new columns. While an **active** listing references the card:

- Still owned by `seller_id`
- Ineligible for XI assign, drills, fusion, evo start, agent sale, academy paths that already block similarly
- On purchase: `owner_id` ← buyer; listing → `sold`

### GameConfig keys (seed)

| Key | Default | Meaning |
|-----|---------|---------|
| `p2p_transfer_market_enabled` | `false` | Feature flag |
| `transfer_listing_slot_cap` | `5` | Max active listings / club |
| `transfer_tax_bps` | `1000` | 10% (basis points) |
| `transfer_price_floor_mult` | `0.75` | × fair value |
| `transfer_price_ceil_mult` | `2.5` | × fair value |
| `transfer_listing_ttl_hours` | `72` | Auto-expire |
| `transfer_relist_cooldown_hours` | `6` | After P2P acquire |

Helper: `p2p_transfer_market_enabled()` BOOLEAN (mirror `economy_v2_enabled` pattern).

### Economy ledger sources (strings)

| Source | Direction | Amount |
|--------|-----------|--------|
| `transfer_buy` | Buyer debit | `−gross` |
| `transfer_sale` | Seller credit | `+net` |

Idempotency keys: `transfer_buy:{listing_id}`, `transfer_sale:{listing_id}`.

## State transitions

```text
                    create_transfer_listing
  (no listing) ────────────────────────────► active
                                                │
                    cancel / expire             │ purchase
                         ▼                      ▼
                    cancelled / expired       sold (+ sales_log)
```

- Terminal states do not return to `active` for the same row; re-list creates a **new** listing row after card is free.

## Validation rules

1. List: owner = seller; not XI / training / active evo / injured / hospital / retired / academy; no other active listing; active listing count &lt; slot cap; price in [floor, ceil]; club not match-locked; flag enabled; re-list cooldown OK.
2. Cancel: listing `active` and `seller_id` matches caller.
3. Purchase: listing `active` and not expired; buyer ≠ seller; buyer coins ≥ price; buyer under senior roster cap; both not match-locked (buyer always; seller should not need action); `expected_price` matches `price_coins`; flag enabled.
4. Expire: `status = active` AND `expires_at ≤ now()` → `expired` (card free).

## RLS

Enable RLS on both new tables. Policies for `anon, authenticated, service_role`:

- `SELECT` active listings (global browse) + own sold/cancelled history as needed
- Mutations **only** via SECURITY DEFINER RPCs (revoke direct INSERT/UPDATE from anon if pattern matches scouting; or allow insert/update only for service paths used by bot key)

Follow `044_scouting_pool.sql` / `030_league_members_rls.sql` patterns; bot uses anon/service as today — grant execute on RPCs; table writes through RPCs preferred.

## Schema guard additions

- `table:public.transfer_listings`
- `table:public.transfer_sales_log`
- `function:create_transfer_listing`
- `function:cancel_transfer_listing`
- `function:purchase_transfer_listing`
- `function:expire_stale_transfer_listings`
- `function:p2p_transfer_market_enabled` (or config-only if helper inlined)
- Policies listed in verify script

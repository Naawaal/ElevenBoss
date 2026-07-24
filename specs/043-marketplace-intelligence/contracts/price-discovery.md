# Contract: Price Discovery

**Feature**: `043-marketplace-intelligence`

## Config

| Key | Default |
|-----|---------|
| `price_discovery_min_sales` | 5 |
| `price_discovery_ovr_window` | 3 |

## Cohort

Completed P2P sales (`transfer_sales_log`) where:

- `role`, `rarity`, `overall` are NOT NULL  
- `role = subject.role` AND `rarity = subject.rarity`  
- `overall` BETWEEN `subject.overall - window` AND `subject.overall + window`

Active listings cohort (for high/low/count): active, non-expired `transfer_listings` joined to current card attrs matching the same cohort rule (live card role/rarity/ovr).

## RPC

### `get_price_discovery(p_role text, p_rarity text, p_overall int) → jsonb`

Or overload accepting `p_card_id uuid` (server loads subject attrs).

### Response shape

```json
{
  "role": "MID",
  "rarity": "Rare",
  "overall": 78,
  "ovr_window": 3,
  "min_sales": 5,
  "sample_size": 12,
  "insufficient_data": false,
  "avg_sale_price": 2100,
  "median_sale_price": 2000,
  "recent_sales": [
    {"gross_price": 2200, "created_at": "…", "overall": 79}
  ],
  "trend": "up",
  "active_count": 4,
  "lowest_active": 1800,
  "highest_active": 2600
}
```

When `sample_size < min_sales`:

- `insufficient_data: true`  
- Omit or null `avg_sale_price`, `median_sale_price`, `trend`  
- MAY still return `active_count` / high / low if active listings exist (real data only)

### Trend

- Window A: median gross of cohort sales in `[now-7d, now)`  
- Window B: median gross in `[now-14d, now-7d)`  
- If either window empty → `trend: null`  
- Else `up` if A > B, `down` if A < B, `flat` if equal

### Recent sales

Bound list (e.g. last 5) by `created_at DESC` — real rows only.

## Pure package mirror

`packages/economy/economy/market_intelligence.py`:

- `cohort_matches(...)`  
- `median_prices(...)` / `average_price(...)`  
- `trend_from_medians(recent, prior)`  
- `insufficient_data(sample_size, min_sales)`  

Bot MAY compute from fetched rows for tests; production Discord path prefers RPC for index use.

## Non-goals

- Invented “recommended list price” as a guaranteed fair quote  
- Using agent-sale amounts as P2P comps

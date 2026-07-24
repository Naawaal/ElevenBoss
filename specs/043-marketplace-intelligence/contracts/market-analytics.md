# Contract: Market Analytics (Ops)

**Feature**: `043-marketplace-intelligence`  
**Audience**: Operators / balancing — not a player Discord dashboard

## RPC

### `get_market_analytics(p_from timestamptz, p_to timestamptz) → jsonb`

Window is half-open `[p_from, p_to)` in UTC.

### Metrics (all from real rows; zeros if empty)

| Metric | Source |
|--------|--------|
| `p2p_sales_count` | COUNT `transfer_sales_log` in window |
| `p2p_gross_volume` | SUM `gross_price` |
| `tax_removed` | SUM `tax_amount` |
| `avg_hours_to_sale` | AVG hours between listing `created_at` and `sold_at` for sales in window (join listings) |
| `listings_created` | COUNT listings with `created_at` in window |
| `listings_expired` | COUNT status=expired with `cancelled_at` or equivalent in window |
| `listings_cancelled` | COUNT status=cancelled in window |
| `listings_sold` | COUNT status=sold with `sold_at` in window |
| `listing_success_rate` | `listings_sold / NULLIF(listings_created, 0)` |
| `agent_sale_count` | COUNT `economy_ledger` where `source='agent_sale'` in window (or equivalent) |
| `agent_coins_paid` | SUM positive coin amounts for those ledger rows |
| `top_positions` | Top N by sales count from sales log `role` (non-null) |
| `top_rarities` | Top N by sales count from `rarity` |
| `highest_transfers` | Top N by `gross_price` |
| `most_active_clubs` | Top N clubs by (sales as seller + buys as buyer) |

### Daily series (optional field)

`daily_volume: [{day, sales_count, gross, tax}]` grouped by UTC date of `transfer_sales_log.created_at` — satisfies long-term collection without a materialize table in MVP.

## Access

- Callable by bot service role / ops scripts via Supabase RPC.  
- No requirement to expose in `/marketplace` UI in this feature.  
- Quickstart documents example invocation.

## Non-goals

- Discord admin embed gallery  
- Estimating missing snapshot breakdowns for legacy NULL rows (exclude from attribute tops; still count money)

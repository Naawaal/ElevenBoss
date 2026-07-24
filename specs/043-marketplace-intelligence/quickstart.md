# Quickstart: Marketplace Intelligence

**Feature**: `043-marketplace-intelligence`  
**Prerequisites**: P2P market from `017` / migration `062` applied; `086` applied and schema verify clean.

## 1. Apply migration

```powershell
# From repo root, with DATABASE_URL in .env (same pattern as other scratch apply scripts)
python scratch/apply_migration_086.py
python scratch/verify_schema_full.py
# or:
# psql $env:DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

Expect: `transfer_sales_log` snapshot columns present; `card_ownership_history` + RLS; RPCs `get_price_discovery`, `get_market_analytics`, ownership helpers; guards green.

## 2. Unit tests (pure)

```powershell
pytest tests/test_market_intelligence.py tests/test_transfer_market_math.py -q
```

Expect: cohort gate, median/average, trend, seven sort modes, Best Value missing-fair ordering.

## 3. Enable P2P (if not already)

Set `game_config.p2p_transfer_market_enabled` → `true` in the target environment.

## 4. Smoke — transfer history + ownership

1. Club A lists an eligible card; Club B buys it.  
2. Query `transfer_sales_log` for that `listing_id`: money columns + **non-null** snapshots (`fair_value_coins`, `rarity`, `role`, `overall`, `potential`, `age_at_sale`).  
3. Query `card_ownership_history` for `card_id`: seller segment closed (`ended_via='p2p_transfer'`), buyer segment open.  
4. Second sale of same card: prior sales log row unchanged; ownership chain length increases.

## 5. Smoke — price discovery UI

1. Seed ≥5 completed sales in one cohort (same role/rarity, OVR within ±3) **or** use SQL inserts of sales log rows with snapshots for a test card cohort.  
2. Open Transfer Board → listing detail: averages/median/active high-low appear.  
3. Clear/thin cohort: UI shows insufficient-data, not invented numbers.

## 6. Smoke — board sort

1. Open Transfer Board with multiple listings.  
2. Cycle sorts (lowest price, ending soon, best value, …): order changes; filters remain.  
3. Empty filter result: empty-state unchanged.

## 7. Smoke — agent sale closes ownership

1. Ensure card has an open ownership segment.  
2. Agent-sell the card.  
3. Card row gone; ownership segment `ended_via='agent_sale'`, `ended_at` set; history still selectable by `card_id`.

## 8. Ops analytics

```sql
SELECT public.get_market_analytics(NOW() - INTERVAL '7 days', NOW());
```

Expect JSON with counts/volumes; zeros acceptable on empty windows; tax_removed matches SUM of sales log tax in the window.

## 9. Regression

- Purchase race / own-buy / tax 90–10 still pass existing tests (`tests/test_transfer_market_race.py`, integrity greps).  
- Agent sale daily cap and scouting purchase still succeed.  
- Hub `/marketplace` defer + hot-path gather unchanged in spirit (no analytics on hub open).

## Contracts

- [transfer-history-enrichment.md](./contracts/transfer-history-enrichment.md)  
- [ownership-history.md](./contracts/ownership-history.md)  
- [price-discovery.md](./contracts/price-discovery.md)  
- [transfer-board-sort.md](./contracts/transfer-board-sort.md)  
- [market-analytics.md](./contracts/market-analytics.md)  
- [marketplace-intelligence-ui.md](./contracts/marketplace-intelligence-ui.md)
)

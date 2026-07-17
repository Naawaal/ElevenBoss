# Quickstart: P2P Transfer Market Validation

**Feature**: `017-player-transfer-market`  
**Date**: 2026-07-14

## Prerequisites

- Migration `062_p2p_transfer_market.sql` applied
- `verify_required_schema.sql` / migration guard passes
- Two test human clubs (Buyer / Seller) with coins; Seller has an eligible bench card
- Feature flag **off** initially

## 1. Pure math (no Discord)

```bash
pytest tests/test_transfer_market_math.py -q
```

Expect: 10% tax net; floor ≤ ceil; prices outside bounds rejected.

## 2. Schema

```bash
python scratch/apply_migration_062.py
python scratch/verify_schema_full.py
```

Expect: `transfer_listings`, `transfer_sales_log`, RPCs present; flag default false.

## 3. Flag off regression (US4)

1. `/marketplace` as Seller  
2. Confirm My Listings disabled / no Transfer Board  
3. Agent sell + scouting still work  

## 4. Enable flag (ops)

Set `game_config.p2p_transfer_market_enabled` → `true` (dashboard or SQL upsert).

## 5. List → cancel (US1 / US3)

1. Seller: My Listings → List Player → pick eligible card → price within shown bounds → confirm  
2. Hub shows `1 / 5`; card absent from agent sell list and cannot enter XI  
3. Cancel listing → card returns; slots `0 / 5`  

## 6. List → buy (US2)

1. Seller lists card at price P  
2. Buyer: Search Market → Transfer Board → filter → Buy Now  
3. Buyer coins −P; Seller coins +(P − tax); card `owner_id` = Buyer  
4. Listing status sold; sales_log has tax_amount  
5. Second Buy Now on same listing fails cleanly  

## 7. Guards

| Case | Expect |
|------|--------|
| Buy own listing | Reject |
| Price below floor | Reject on create |
| Buyer at `senior_roster_cap` | Reject purchase |
| Agent sell listed card | Reject |
| Relist within 6h of P2P buy | Reject |
| Wait past `expires_at` / run expiry job | Listing expired; card back with seller |

## 8. Race (optional staging)

Two buyers confirm same listing nearly simultaneously → exactly one success; loser sees already sold; no double debit.

## Done when

Quickstart 1–7 pass with flag toggle; agent/scouting unchanged when flag off.

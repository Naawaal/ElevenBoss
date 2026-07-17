# Quickstart: Contract & Wage Validation

**Feature**: `019-contract-wage-system`  
**Date**: 2026-07-14

## Prerequisites

- Migration `063_contract_wage_system.sql` applied  
- `verify_required_schema.sql` passes  
- One human test club with Starting XI + known coin balance  
- Flag **off** initially  

## 1. Pure math

```bash
pytest tests/test_wage_payroll_math.py -q
```

Expect: OVR wage formula; bill_scale; grace/block windows; strike thresholds.

## 2. Schema

```bash
python scratch/apply_migration_063.py
python scratch/verify_schema_full.py
```

Expect: `payroll_debt` / `payroll_strikes` on `players`; `payroll_runs`; `process_weekly_payroll` / `process_club_weekly_payroll`; flag default false.

## 3. Flag off (SC-005)

1. `/profile` → Finances → wages still **not auto-deducted**  
2. Run `process_weekly_payroll` → no coin change (or skipped_flag only)  

## 4. Enable flag (ops)

```sql
UPDATE game_config SET value_json = 'true'::jsonb WHERE key = 'wages_payroll_enabled';
-- optional soft week:
UPDATE game_config SET value_json = '0.5'::jsonb WHERE key = 'wages_payroll_bill_scale';
```

## 5. Paid payroll (US2)

1. Note coins C and Finances bill B  
2. `SELECT process_club_weekly_payroll(<club>, <week_key>);`  
3. Coins = C − (debt_before + B)×scale path; debt 0; strikes 0; `payroll_runs` row `paid`  
4. Re-run same week → idempotent, no second debit  

## 6. Partial / unpaid (US3)

1. Set club coins below bill (via test-only or spend)  
2. Process payroll → status `partial`; debt > 0; strikes ≥ 1  
3. Finances shows debt + strikes  
4. With strikes ≥ 2, friendly match blocked; league/bot still allowed  
5. With strikes ≥ 3, P2P list / scout blocked; agent sale OK  

## 7. Contract teeth (US4)

1. Set an XI card `contract_expires_at` to now − 1 day (in grace) → match still OK, warning in Finances/profile  
2. Set to now − 10 days (past 7d grace) → cannot assign to XI / match blocked with renew/replace message  
3. Renew via profile → expires extended; block clears  
4. Age ≥ 35 renew still rejected  

## 8. AI exempt (D9)

Process payroll for `is_ai` club → `skipped_ai`; coins unchanged.

## 9. RPC strike bypass check (T037)

With `payroll_strikes ≥ market_block`, direct RPC `create_transfer_listing` / scout spend rejects even if Discord UI is skipped.

## Done when

Steps 1–9 pass; flag toggle restores forecast-only; no direct `players.coins` writes outside economy pipe; no morale / auto-release paths.

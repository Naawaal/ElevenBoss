# Quickstart: League Dynamics Validation

**Feature**: `020-league-dynamics`  
**Date**: 2026-07-15

## Prerequisites

- Migration `064_league_dynamics.sql` applied  
- `verify_required_schema.sql` passes  
- Test guild with `/league` channel + Journal capability  
- Flag **off** initially  
- Prefer starting a Dynamics pilot near **00:00 UTC** so MD1 is ~24h

## 1. Pure math

```bash
pytest tests/test_league_dynamics_windows.py tests/test_seasonal_promo_relegation.py tests/test_momd_selection.py -q
```

Expect: UTC window assignment; fixed-2 promo with n&lt;4 skip; MoMD eligibility excludes auto-sim/draws/AI winners; deterministic ties.

## 2. Schema

```bash
python scratch/apply_migration_064.py
python scratch/verify_schema_full.py
```

Expect: `pacing_mode`, `division_tier`, `resolved_by`, `seasonal_division_tier`, `league_matchday_manager_awards`, MoMD RPC, flag default false.

## 3. Flag off — grandfather (SC-006)

1. Leave an **active legacy** season (or start one with flag off).  
2. Confirm `pacing_mode='legacy'`, rolling windows, 10-min auto-sim still touches it.  
3. Confirm fixtures’ `window_end` unchanged after migration.

## 4. Enable flag (ops)

```sql
UPDATE game_config SET value_json = 'true'::jsonb WHERE key = 'league_dynamics_enabled';
```

## 5. Dynamics single division (≤8 humans)

1. Register ≤8 humans; admin start season.  
2. Expect: `pacing_mode='dynamics'`, `duration_days=14`, `total_matchdays=14`, one tier, bot fill to 8, midnight-aligned `window_end`.  
3. Hub shows 00:00 UTC deadline + Division 1.  
4. Play one fixture manually → `resolved_by='manual'`.  
5. Leave one expired → after 00:05 tick → `resolved_by='auto_sim'`.

## 6. MoMD (US4)

1. Complete a matchday with ≥1 manual human win and ≥1 auto-sim.  
2. `award_manager_of_the_matchday` → coins to manual winner only; Journal line once.  
3. Re-call RPC → `already_awarded`, no second credit.  
4. All-auto-sim matchday → `no_eligible`, no Journal MoMD.

## 7. Multi-division seating (US3)

1. Register 9+ humans; start season.  
2. Expect Div1 = 8 humans (or fewer only if fees skip — refill bots), Div2 = remainder + bots to 8.  
3. Standings hub shows viewer’s tier only by default.

## 8. Promo/releg (end of season)

1. Complete / force-end a two-tier Dynamics season.  
2. Bottom 2 Div1 humans → `league_members.seasonal_division_tier=2`.  
3. Top 2 Div2 humans → `tier=1`.  
4. Next Dynamics start reseats accordingly.

## 9. Player-facing copy

- No new slash commands.  
- Journal MoMD density = at most one line per matchday when awarded.

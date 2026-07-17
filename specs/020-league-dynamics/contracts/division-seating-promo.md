# Contract: Division Seating & Promotion/Relegation

**Feature**: `020-league-dynamics`

## Pure helper — `seat_humans_into_divisions(human_ids_ordered, clubs_per_div=8) → list[list[id]]`

### Ordering input

Prefer (stable):

1. Ascending `league_members.seasonal_division_tier`
2. Then last season finish rank within tier if known
3. Else registration / list order

### Partition

- Chunk humans into groups of at most `clubs_per_div` (8).
- Tier index 1..K for each chunk.
- Caller bot-fills each chunk to length 8 with new AI clubs.

### First Dynamics season

Everyone with `seasonal_division_tier=1` default → first 8 humans Div 1, next 8 Div 2, etc. (Q2=A).

## Pure helper — `compute_fixed_promo_relegation(human_standings_sorted, spots=2) → {promoted, relegated, retained}`

- Input: humans only, already sorted Pts→GD→GF (same as seasonal table).
- `n < 4`: return empty promo/releg (edge case).
- Else: top `spots` / bottom `spots` with no overlap (if `2*spots > n`, shrink spots to 1).

**Do not call** weekly `compute_promotions_relegations` (20%).

## Adjacent swap — `apply_seasonal_promotion_relegation(p_season_id)`

### Preconditions

- Season `status='completed'` (or called at end of complete path before marking inactive).
- Dynamics season (legacy no-op).

### Effects

For each tier `t` from 1..max-1:

1. Build human standings for tier `t` and `t+1` from fixtures.
2. Relegated = bottom 2 of `t`; promoted = top 2 of `t+1`.
3. `UPDATE league_members SET seasonal_division_tier = t+1` for relegated (guild_id of season).
4. `UPDATE league_members SET seasonal_division_tier = t` for promoted.

AI participants ignored. Idempotent if already applied (optional `config_json.promo_applied` guard).

## Prizes

`distribute_season_prizes(p_season_id)`:

- For each distinct `division_tier` on participants:
  - Build human standings **within tier only**
  - Pay 60/25/10 + participation using existing pool rules (pool may be shared or per-tier — **v1: run existing pool math once per tier** using same `league_season_prize_pool_base`, meta includes `division_tier`)
- Then call promo/releg persist.

## Standings UX

- `fetch_standings(db, season_id, division_tier=None)` — default viewer’s own tier; admin/Journal may post all tiers sequentially.

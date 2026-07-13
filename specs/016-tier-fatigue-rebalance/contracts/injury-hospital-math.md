# Contract: Injury Chance & Hospital Recovery Math

**Feature**: `016-tier-fatigue-rebalance`  
**Pure module**: `packages/player_engine/player_engine/injury_math.py`  
**SQL**: `process_post_match_injuries`, `admit_to_hospital`, overflow untreated days, backfill RPC

## Injury probability

```text
injury_base(tier) = {1: 0.0025, 2: 0.0040, 3: 0.0060}

fatigue_mod = (100 - fatigue) * 0.0003
# retain existing age_mod / phy_mod helpers

chance = max(0, injury_base(tier) + fatigue_mod + age_mod + phy_mod)
```

**Soft-caps retained**:
- Eligible only if fatigue &lt; 75
- At most one injury per club per match (`select_post_match_injury`)

`select_post_match_injury` / `injury_chance` gain an `intensity_tier` (or `injury_base`) parameter.

## Hospital / untreated recovery days

```text
moderate_base(tier) = {1: 3, 2: 5, 3: 8}
sev_mult(severity) = {1 Minor: 0.33, 2 Moderate: 1.0, 3 Major: 2.5}

raw_days = (moderate_base(tier) * sev_mult(severity)) / (1 + 0.2 * hospital_level)
days = max(1, ceil(raw_days))   # while still injured
```

Untreated overflow uses `hospital_level = 0`.

## Anchors

| Case | Expected days |
|------|----------------|
| Tier 3 Moderate, H=5 | `ceil(8 / 2) = 4` |
| Tier 1 Moderate, H=0 | `ceil(3) = 3` |
| Tier 3 Major, H=0 | `ceil(20) = 20` |

## Fair helpers

Update `fair_hospital_*` / `fair_overflow_remaining_days` to take `(tier_intensity, severity)` (or precomputed new_total) instead of flat `BASE_RECOVERY_DAYS` 1/4/7.

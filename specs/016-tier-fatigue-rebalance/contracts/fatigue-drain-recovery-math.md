# Contract: Fatigue Drain & Daily Recovery Math

**Feature**: `016-tier-fatigue-rebalance`  
**Pure module**: `packages/player_engine/player_engine/fatigue.py` (+ intensity helper)  
**SQL**: `process_daily_recovery` (passive); starter drains remain bot-authored via `apply_match_fatigue`

## Match drain

```text
tactic_mod(stance) =
  attack  → +4
  defend  → -2
  neutral → 0

tier_base(tier) = {1: 8, 2: 12, 3: 16}

drain = max(0, half_up_round(tier_base(tier) - phy * 0.10 + tactic_mod(stance)))
```

**Removed**: flat `intensity` boolean (+5); rating-gap trigger in `match_rewards`.

**Call site**: `injury_rpc.build_starter_drains(..., intensity_tier=N)` → `match_fatigue_drain(..., tier=N)`.

## Daily natural recovery (non-hospital)

```text
passive_base(tier) = {1: 35, 2: 25, 3: 15}

recovery = passive_base(tier) + (training_ground_level * 2)
fatigue' = min(100, fatigue + recovery)
```

**Unchanged**: hospital daily fatigue +45; bench +25; Recovery Session +40.

## Examples (acceptance anchors)

| Case | Expected |
|------|----------|
| Tier 1, PHY 70, Neutral | `max(0, round(8 - 7 + 0)) = 1` |
| Tier 3, TG 3 passive | `15 + 6 = 21` |
| Tier 1, TG 3 passive | `35 + 6 = 41` |

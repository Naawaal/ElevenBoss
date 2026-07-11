# Contract: Transition probability floor

## Scope

`packages/match_engine/match_engine/v2_simulator.py` — `_probability_floor` / `_roll_chance`, plus possession tick completeness on ball-winning transitions.

## Rule

After computing the raw transition chance and before the RNG roll:

```text
chance = max(0.05, min(0.95, chance))
```

`_probability_floor(...)` MUST always return **0.05**. Remove the branch that returns **0.02** when the attacker–defender stat gap exceeds 15.

## Possession tick completeness (required for SC-003)

Possession ticks MUST be recorded whenever a side meaningfully wins the ball, not only on midfield contest resolution:

| Transition | Record possession for |
|------------|------------------------|
| Midfield win / loss | Winner (existing) |
| Midfield → SET_PIECE (foul) | Attacking side (set-piece taker) |
| BUILD_UP fail → COUNTER_ATTACK | New attacking side (countering team) |

Without the set-piece / counter ticks, a side can create chances yet show **0%** possession.

## Applies to

All contested rolls that already go through `_roll_chance` (midfield win, build-up, attack progression, scoring, counter, etc.).

## Must not change

- Phase enum / state machine topology
- Stagnation counter semantics
- Momentum decay schedule
- Event yield shapes

## Observable outcomes

- Post-match possession from `MatchLiveStats` (same live counters managers watched)
- Across ≥20 full sims with valid 11-a-side XIs: **no** exact `0% / 100%` possession splits
- Heavily favored sides still win a clear majority of mismatched matches

## Non-goals

- Soft-clamping displayed possession without changing rolls
- Rewriting possession to legacy `simulator.py` formula
- New `game_config` rows (constant in code is enough for v1)

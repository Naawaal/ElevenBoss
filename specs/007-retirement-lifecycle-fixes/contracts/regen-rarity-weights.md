# Contract: Regen Rarity Weights

**Module**: `packages/player_engine/player_engine/regen_pool.py`  
**Caller**: `apps/discord_bot/tasks/regen_pool_job.py` (unchanged flow)  
**Feature**: `007-retirement-lifecycle-fixes`

## API

```text
regen_rarity_for_ovr(retired_ovr: int, rng: random.Random) -> Literal["Common","Rare","Epic"]
```

Used by `generate_regen_from_retired` instead of the inverted nested-probability chain.

## Weights (exact)

| `retired_ovr` | Epic | Rare | Common |
|---------------|------|------|--------|
| ≥ 85 | 0.50 | 0.50 | 0.00 |
| 80–84 | 0.00 | 0.60 | 0.40 |
| 75–79 | 0.00 | 0.20 | 0.80 |
| &lt; 75 | N/A — spawn job should not call; if called, return `"Common"` defensively |

Implementation: single `rng.random()` with cumulative thresholds (or `rng.choices` with weights).

## Unchanged

- Position inheritance, age 16–19, target OVR band 55–70, potential jitter
- Spawn eligibility threshold (≥ 75), pool cap, idempotency per `source_card_id`
- `CreatedPlayerCard` / scouting payload shape

## Tests

- Seeded distribution: n≥200 per band → frequencies within ±5 pp of weights (SC-004/005)
- ≥85 sample: zero Commons

## Non-goals

- Marketplace UI changes
- Price formula changes (price already takes rarity as input)
- Legendary rarity for regens

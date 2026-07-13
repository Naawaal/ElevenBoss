# Contract: Intensity Tier Mapping

**Feature**: `016-tier-fatigue-rebalance`  
**Consumers**: migration backfill, `weekly_league_reset_job`, pure `intensity_tier_for_division`, SQL RPCs, Discord embeds

## Function (pure)

```text
intensity_tier_for_division(division: str | None) -> Literal[1, 2, 3]
```

| Division | Tier |
|----------|------|
| Grassroots, Amateur | 1 |
| Semi-Pro, Professional | 2 |
| Elite, Legendary | 3 |
| anything else / None | 1 |

## Persistence

- Column: `players.intensity_tier SMALLINT NOT NULL DEFAULT 1`
- Writers: migration `061` backfill; Monday `weekly_league_reset_job` after division settlement
- Readers: `process_daily_recovery`, admit/injury recovery SQL, bot match fitness, Hospital/profile UI

## UI labels (suggested)

| Tier | Short label | Intensity vibe |
|------|-------------|----------------|
| 1 | Low | Forgiving |
| 2 | Medium | Rotation recommended |
| 3 | High | Deep squad required |

Display may include current `division` name alongside the vibe line.

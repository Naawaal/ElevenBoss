# Monday Intake Soak Report — YA V2

**Status**: PENDING first Monday 00:00 UTC after V2 flag enable  
**Flag**: `youth_academy_v2_enabled=true` (confirmed 2026-08-04)  
**Jobs**: `youth_intake_job` (Mon 00:00 UTC), `academy_growth_job` (daily)

## Capture checklist (fill after job)

| Metric | Value | Notes |
|--------|-------|-------|
| Run timestamp (UTC) | | |
| Eligible human managers | | |
| Processed (new week) | | |
| Skipped (already_processed) | | |
| Failed | | |
| Prospects seated | | |
| Capacity-blocked clubs | | |
| Illegal POT rejects | | |
| Legendary seated | | If >0 early → review kill switch |
| DM success / Forbidden | | |
| Job duration / exceptions | | bot logs |

## Rarity mix by YA level

| Level | Common | Rare | Epic | Legendary |
|-------|--------|------|------|-----------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

## SQL helpers (post-intake)

```sql
-- Seated this week
SELECT intake_week, COUNT(*), SUM(cardinality(card_ids))
FROM youth_intake_log
WHERE intake_week = public.current_intake_week()
GROUP BY 1;

-- Rarity of academy cards seated this week
SELECT pc.rarity, p.youth_academy_level, COUNT(*)
FROM youth_intake_log y
JOIN LATERAL unnest(y.card_ids) AS cid ON true
JOIN player_cards pc ON pc.id = cid
JOIN players p ON p.discord_id = y.owner_id
WHERE y.intake_week = public.current_intake_week()
GROUP BY 1, 2
ORDER BY 2, 1;
```

## Decision gate

- P0/P1 found? ___  
- Legendary anomaly? ___  
- Ready for second soak? ___  

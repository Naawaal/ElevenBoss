# Quickstart: Bench Rest Clarity

**Feature**: `014-bench-rest-clarity`

## Prerequisites

- Migration `059` applied (`fatigue_applied_at` on `match_history`)
- Bot redeployed on Bisup after Python changes
- Confirm `game_config.fatigue_bench_per_match` is 25 (already live as of 2026-07-12)

## Manual verify

1. Pick an unused healthy reserve with fatigue **~50–70** and among the **7 highest overall** unused cards.
2. Play one **bot** match (do not use friendly).
3. Expect: that card’s fatigue **+25** (or to 100), and match-end line mentioning bench rest.
4. Force a fitness failure in staging (optional): XP still applies; `fatigue_applied_at` stays null; retry path applies fatigue once without double XP.

## Ops SQL smoke

```sql
SELECT key, value_json FROM game_config WHERE key = 'fatigue_bench_per_match';
-- optional: SELECT id, xp_applied_at, fatigue_applied_at FROM match_history
--   WHERE player_id = <discord_id> ORDER BY created_at DESC LIMIT 5;
```

## Out of scope checks

- Friendlies must **not** change fatigue
- 8th+ lower-OVR unused may still not rest (by design until product expands)

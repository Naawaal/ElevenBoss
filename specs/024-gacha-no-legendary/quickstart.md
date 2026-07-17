# Quickstart: Gacha Pack Epic Cap

**Feature**: `024-gacha-no-legendary`

## Prerequisites

- Migration `068_pack_epic_cap_odds.sql` applied (or package defaults alone for local unit tests)
- Bot with updated `store_cog` + `gacha` package

## 1. Unit / simulation

```bash
pytest tests/test_pack_configs.py -q
```

Expect: standard weights `(60, 30, 10)`; ≥10k rolls → **0** Legendary; Epic ~10%.

## 2. Store claim (manual)

1. `/store` → read Daily Gacha Pack copy — Epic max, no Legendary promise.
2. Claim pack when ready → all 5 cards Common/Rare/Epic.
3. Repeat a few times; no Legendary.

## 3. Regression — owned Legendary

1. Club with an existing Legendary card → still shows Legendary in squad/profile.
2. If thank-you gift enabled and eligible → claim still grants Legendary (not via pack).

## 4. Config smoke (optional)

```sql
-- Temporarily break config; pack claim should still never drop Legendary
UPDATE game_config SET value_json = '["Common","Rare","Epic","Legendary"]'
WHERE key = 'pack_standard_rarities';
UPDATE game_config SET value_json = '[60,30,8,2]'
WHERE key = 'pack_standard_rarity_weights';
```

Claim a pack → still no Legendary (sanitize). Restore Epic-capped values afterward.

## Rollback

Restore package `60/30/8/2` + config keys; Store copy. No player-card migration to reverse.

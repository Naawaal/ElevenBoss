# Contract: game_config pack odds

**Feature**: `024-gacha-no-legendary`  
**Migration**: `068_pack_epic_cap_odds.sql` (planned)

## Seeds

```sql
INSERT INTO public.game_config (key, value_json) VALUES
  ('pack_standard_rarities', '["Common","Rare","Epic"]'),
  ('pack_standard_rarity_weights', '[60,30,10]')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;
```

Use **DO UPDATE** so environments that still have old docs/values get the Epic-capped mix (Legendary removed from pack odds).

## Bot read path

On daily pack claim (`store_cog`):

1. `get_game_config('pack_standard_rarities')` → list[str] or None
2. `get_game_config('pack_standard_rarity_weights')` → list[int] or None
3. Pass both into `generate_pack(..., rarities=..., rarity_weights=...)` when valid; else omit (package defaults)
4. Package sanitize still strips Legendary if ops re-adds it

## Failure mode

Any parse error → omit override; pack still Epic-capped via package defaults. Log at debug/warning; do not fail the claim.

## Verify

Optional: migration DO block asserts keys exist. Extend `verify_required_schema.sql` only if the project already guards config keys that way; otherwise package defaults alone keep bot safe.

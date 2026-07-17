-- 068_pack_epic_cap_odds.sql
-- Standard pack odds: Epic max (no Legendary). Fold former 2% into Epic → 60/30/10.

INSERT INTO public.game_config (key, value_json) VALUES
    ('pack_standard_rarities', '["Common","Rare","Epic"]'::jsonb),
    ('pack_standard_rarity_weights', '[60,30,10]'::jsonb)
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

DO $$
BEGIN
    IF public.get_game_config('pack_standard_rarities') IS NULL THEN
        RAISE EXCEPTION 'Migration 068 guard failed — pack_standard_rarities missing';
    END IF;
    IF public.get_game_config('pack_standard_rarity_weights') IS NULL THEN
        RAISE EXCEPTION 'Migration 068 guard failed — pack_standard_rarity_weights missing';
    END IF;
END;
$$;

-- 085: Standard pack Epic drop rate 10% → 5% (Rare absorbs the difference → 60/35/5).

INSERT INTO public.game_config (key, value_json) VALUES
    ('pack_standard_rarities', '["Common","Rare","Epic"]'::jsonb),
    ('pack_standard_rarity_weights', '[60,35,5]'::jsonb)
ON CONFLICT (key) DO UPDATE
SET value_json = EXCLUDED.value_json;

DO $$
DECLARE
    v_w jsonb;
BEGIN
    v_w := public.get_game_config('pack_standard_rarity_weights');
    IF v_w IS NULL OR v_w <> '[60,35,5]'::jsonb THEN
        RAISE EXCEPTION 'Migration 085 guard failed — pack_standard_rarity_weights expected [60,35,5], got %', v_w;
    END IF;
END $$;

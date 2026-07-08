-- 045: Fix card_xp_age_multiplier — game_config stores decimal multipliers (1.5),
-- not integer percents (150). get_game_config_int fails with 22P02 on "1.5".

CREATE OR REPLACE FUNCTION public.card_xp_age_multiplier(p_age INTEGER)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_youth NUMERIC := public.get_game_config_numeric('age_xp_mult_youth', 1.5);
    v_early NUMERIC := public.get_game_config_numeric('age_xp_mult_early_prime', 1.2);
    v_late NUMERIC := public.get_game_config_numeric('age_xp_mult_late_prime', 1.0);
    v_vet NUMERIC := public.get_game_config_numeric('age_xp_mult_veteran', 0.7);
    v_ret NUMERIC := public.get_game_config_numeric('age_xp_mult_retiring', 0.4);
BEGIN
    IF p_age <= 21 THEN
        RETURN v_youth;
    ELSIF p_age <= 26 THEN
        RETURN v_early;
    ELSIF p_age <= 30 THEN
        RETURN v_late;
    ELSIF p_age <= 34 THEN
        RETURN v_vet;
    ELSE
        RETURN v_ret;
    END IF;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.card_xp_age_multiplier(INTEGER) TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.card_xp_age_multiplier(integer)') IS NULL THEN
        RAISE EXCEPTION '045 guard: card_xp_age_multiplier(integer) missing';
    END IF;
    IF public.card_xp_age_multiplier(19) <> 1.5 THEN
        RAISE EXCEPTION '045 guard: card_xp_age_multiplier(19) expected 1.5 got %', public.card_xp_age_multiplier(19);
    END IF;
    IF public.card_xp_age_multiplier(24) <> 1.2 THEN
        RAISE EXCEPTION '045 guard: card_xp_age_multiplier(24) expected 1.2 got %', public.card_xp_age_multiplier(24);
    END IF;
END $$;

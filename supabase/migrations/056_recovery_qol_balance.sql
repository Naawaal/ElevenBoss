-- 056: Recovery QoL balance — injury 1/4/7, passive base 25, bench 25, drain 18
-- Forward-only: does not rewrite open hospital_patients ETAs.

INSERT INTO public.game_config (key, value_json) VALUES
    ('fatigue_passive_base', '25'),
    ('fatigue_bench_per_match', '25'),
    ('fatigue_base_drain', '18')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

-- ---------------------------------------------------------------------------
-- process_post_match_injuries — base days 1 / 4 / 7
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_post_match_injuries(
    p_owner_id BIGINT,
    p_injuries JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_injury JSONB;
    v_card_id UUID;
    v_tier INTEGER;
    v_hospital INTEGER;
    v_max_beds INTEGER;
    v_current_beds INTEGER;
    v_base_days INTEGER;
    v_recovery_days INTEGER;
    v_admitted JSONB := '[]'::JSONB;
    v_overflow JSONB := '[]'::JSONB;
BEGIN
    SELECT COALESCE(hospital_level, 0) INTO v_hospital
    FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Manager not found';
    END IF;

    v_max_beds := v_hospital + 1;

    SELECT COUNT(*)::INTEGER INTO v_current_beds
    FROM public.hospital_patients
    WHERE owner_id = p_owner_id AND discharge_date IS NULL;

    FOR v_injury IN SELECT * FROM jsonb_array_elements(COALESCE(p_injuries, '[]'::JSONB))
    LOOP
        v_card_id := (v_injury->>'player_card_id')::UUID;
        v_tier := (v_injury->>'tier')::INTEGER;
        IF v_tier IS NULL OR v_tier < 1 OR v_tier > 3 THEN
            CONTINUE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM public.player_cards
            WHERE id = v_card_id AND owner_id = p_owner_id AND COALESCE(is_retired, FALSE) = FALSE
        ) THEN
            CONTINUE;
        END IF;

        v_base_days := CASE v_tier WHEN 1 THEN 1 WHEN 2 THEN 4 ELSE 7 END;
        v_recovery_days := CEIL(v_base_days::NUMERIC / (1 + 0.2 * v_hospital))::INTEGER;

        IF v_current_beds < v_max_beds
           AND NOT EXISTS (
               SELECT 1 FROM public.hospital_patients
               WHERE player_card_id = v_card_id AND discharge_date IS NULL
           ) THEN
            INSERT INTO public.hospital_patients (
                owner_id, player_card_id, injury_tier, expected_recovery_date
            ) VALUES (
                p_owner_id, v_card_id, v_tier,
                NOW() + (v_recovery_days || ' days')::INTERVAL
            );

            UPDATE public.player_cards
            SET injury_tier = v_tier,
                injury_started_at = NOW(),
                injury_recovery_days = v_recovery_days,
                in_hospital = TRUE
            WHERE id = v_card_id;

            v_admitted := v_admitted || jsonb_build_array(jsonb_build_object(
                'player_card_id', v_card_id,
                'tier', v_tier,
                'recovery_days', v_recovery_days
            ));
            v_current_beds := v_current_beds + 1;
        ELSE
            UPDATE public.player_cards
            SET injury_tier = v_tier,
                injury_started_at = NOW(),
                injury_recovery_days = v_base_days,
                in_hospital = FALSE
            WHERE id = v_card_id;

            v_overflow := v_overflow || jsonb_build_array(jsonb_build_object(
                'player_card_id', v_card_id,
                'tier', v_tier,
                'recovery_days', v_base_days
            ));
        END IF;
    END LOOP;

    RETURN jsonb_build_object('admitted', v_admitted, 'overflow', v_overflow);
END;
$$;

-- ---------------------------------------------------------------------------
-- admit_to_hospital — base days 1 / 4 / 7
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admit_to_hospital(
    p_owner_id BIGINT,
    p_player_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_tier INTEGER;
    v_hospital INTEGER;
    v_max_beds INTEGER;
    v_current_beds INTEGER;
    v_base_days INTEGER;
    v_recovery_days INTEGER;
BEGIN
    SELECT injury_tier INTO v_tier
    FROM public.player_cards
    WHERE id = p_player_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND OR v_tier IS NULL THEN
        RAISE EXCEPTION 'Card is not injured or not owned';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.hospital_patients
        WHERE player_card_id = p_player_card_id AND discharge_date IS NULL
    ) THEN
        RAISE EXCEPTION 'Already in hospital';
    END IF;

    SELECT COALESCE(hospital_level, 0) INTO v_hospital
    FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;

    v_max_beds := v_hospital + 1;
    SELECT COUNT(*)::INTEGER INTO v_current_beds
    FROM public.hospital_patients
    WHERE owner_id = p_owner_id AND discharge_date IS NULL;

    IF v_current_beds >= v_max_beds THEN
        RAISE EXCEPTION 'Hospital beds full';
    END IF;

    v_base_days := CASE v_tier WHEN 1 THEN 1 WHEN 2 THEN 4 ELSE 7 END;
    v_recovery_days := CEIL(v_base_days::NUMERIC / (1 + 0.2 * v_hospital))::INTEGER;

    INSERT INTO public.hospital_patients (
        owner_id, player_card_id, injury_tier, expected_recovery_date
    ) VALUES (
        p_owner_id, p_player_card_id, v_tier,
        NOW() + (v_recovery_days || ' days')::INTERVAL
    );

    UPDATE public.player_cards
    SET in_hospital = TRUE,
        injury_recovery_days = v_recovery_days
    WHERE id = p_player_card_id;

    RETURN jsonb_build_object(
        'player_card_id', p_player_card_id,
        'recovery_days', v_recovery_days,
        'tier', v_tier
    );
END;
$$;

-- Align bench fallback with new default (config upsert is source of truth).
CREATE OR REPLACE FUNCTION public.apply_match_fatigue(
    p_owner_id BIGINT,
    p_starter_drains JSONB,
    p_bench_ids UUID[] DEFAULT ARRAY[]::UUID[]
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_key TEXT;
    v_drain INTEGER;
    v_card_id UUID;
    v_bench UUID;
    v_bench_amt INTEGER;
    v_updated INTEGER := 0;
BEGIN
    v_bench_amt := public.get_game_config_int('fatigue_bench_per_match', 25)::INTEGER;

    FOR v_key, v_drain IN
        SELECT key, GREATEST(0, (value #>> '{}')::INTEGER)
        FROM jsonb_each(COALESCE(p_starter_drains, '{}'::JSONB))
    LOOP
        v_card_id := v_key::UUID;
        UPDATE public.player_cards
        SET fatigue = GREATEST(0, LEAST(100, fatigue - v_drain))
        WHERE id = v_card_id
          AND owner_id = p_owner_id
          AND COALESCE(is_retired, FALSE) = FALSE;
        IF FOUND THEN
            v_updated := v_updated + 1;
        END IF;
    END LOOP;

    IF p_bench_ids IS NOT NULL THEN
        FOREACH v_bench IN ARRAY p_bench_ids
        LOOP
            UPDATE public.player_cards
            SET fatigue = GREATEST(0, LEAST(100, fatigue + v_bench_amt))
            WHERE id = v_bench
              AND owner_id = p_owner_id
              AND COALESCE(is_retired, FALSE) = FALSE
              AND injury_tier IS NULL;
            IF FOUND THEN
                v_updated := v_updated + 1;
            END IF;
        END LOOP;
    END IF;

    RETURN jsonb_build_object('updated', v_updated);
END;
$$;

DO $$
BEGIN
    IF public.get_game_config_int('fatigue_passive_base', 0) <> 25 THEN
        RAISE EXCEPTION 'Migration 056 guard failed — fatigue_passive_base != 25';
    END IF;
    IF public.get_game_config_int('fatigue_bench_per_match', 0) <> 25 THEN
        RAISE EXCEPTION 'Migration 056 guard failed — fatigue_bench_per_match != 25';
    END IF;
    IF public.get_game_config_int('fatigue_base_drain', 0) <> 18 THEN
        RAISE EXCEPTION 'Migration 056 guard failed — fatigue_base_drain != 18';
    END IF;
END $$;

-- 061: Division-tier fatigue / injury rebalance (016)
-- intensity_tier on players; tiered drain/passive/injury/hospital; fair backfill + fatigue floor.

-- ---------------------------------------------------------------------------
-- Column + backfill from settled division
-- ---------------------------------------------------------------------------
ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS intensity_tier SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_intensity_tier_check;

ALTER TABLE public.players
    ADD CONSTRAINT players_intensity_tier_check
    CHECK (intensity_tier BETWEEN 1 AND 3);

UPDATE public.players
SET intensity_tier = CASE COALESCE(division, 'Grassroots')
    WHEN 'Grassroots' THEN 1
    WHEN 'Amateur' THEN 1
    WHEN 'Semi-Pro' THEN 2
    WHEN 'Professional' THEN 2
    WHEN 'Elite' THEN 3
    WHEN 'Legendary' THEN 3
    ELSE 1
END;

INSERT INTO public.game_config (key, value_json) VALUES
    ('fatigue_intensity_drain_bases', '{"1":8,"2":12,"3":16}'::jsonb),
    ('fatigue_intensity_passive_bases', '{"1":35,"2":25,"3":15}'::jsonb),
    ('fatigue_passive_tg_per_level', '2'::jsonb),
    ('fatigue_base_drain', '8'::jsonb),
    ('fatigue_passive_base', '35'::jsonb),
    ('injury_intensity_bases', '{"1":0.0025,"2":0.004,"3":0.006}'::jsonb),
    ('hospital_moderate_bases', '{"1":3,"2":5,"3":8}'::jsonb)
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

-- ---------------------------------------------------------------------------
-- Helpers (SQL mirrors of player_engine)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.intensity_recovery_days(
    p_severity INTEGER,
    p_intensity_tier INTEGER,
    p_hospital_level INTEGER
) RETURNS INTEGER
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_moderate NUMERIC;
    v_sev NUMERIC;
    v_days INTEGER;
BEGIN
    v_moderate := CASE GREATEST(1, LEAST(3, COALESCE(p_intensity_tier, 1)))
        WHEN 1 THEN 3
        WHEN 2 THEN 5
        ELSE 8
    END;
    v_sev := CASE GREATEST(1, LEAST(3, COALESCE(p_severity, 2)))
        WHEN 1 THEN 0.33
        WHEN 2 THEN 1.0
        ELSE 2.5
    END;
    v_days := CEIL((v_moderate * v_sev) / (1 + 0.2 * GREATEST(0, COALESCE(p_hospital_level, 0))))::INTEGER;
    RETURN GREATEST(1, v_days);
END;
$$;

CREATE OR REPLACE FUNCTION public.intensity_untreated_base_days(
    p_severity INTEGER,
    p_intensity_tier INTEGER
) RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_moderate NUMERIC;
    v_sev NUMERIC;
BEGIN
    v_moderate := CASE GREATEST(1, LEAST(3, COALESCE(p_intensity_tier, 1)))
        WHEN 1 THEN 3
        WHEN 2 THEN 5
        ELSE 8
    END;
    v_sev := CASE GREATEST(1, LEAST(3, COALESCE(p_severity, 2)))
        WHEN 1 THEN 0.33
        WHEN 2 THEN 1.0
        ELSE 2.5
    END;
    RETURN v_moderate * v_sev;
END;
$$;

-- ---------------------------------------------------------------------------
-- process_daily_recovery — tier passive + TG×2
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_daily_recovery()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_hosp INTEGER;
    v_fatigue_n INTEGER;
    v_discharged INTEGER;
    v_untreated INTEGER;
BEGIN
    v_hosp := public.get_game_config_int('fatigue_hospital_per_day', 45)::INTEGER;

    UPDATE public.player_cards pc
    SET fatigue = LEAST(
        100,
        pc.fatigue + CASE
            WHEN pc.in_hospital THEN v_hosp
            ELSE (
                CASE COALESCE(p.intensity_tier, 1)
                    WHEN 1 THEN 35
                    WHEN 2 THEN 25
                    ELSE 15
                END
                + COALESCE(p.training_ground_level, 1) * 2
            )
        END
    )
    FROM public.players p
    WHERE pc.owner_id = p.discord_id
      AND pc.fatigue < 100
      AND COALESCE(pc.is_retired, FALSE) = FALSE;
    GET DIAGNOSTICS v_fatigue_n = ROW_COUNT;

    UPDATE public.hospital_patients hp
    SET discharge_date = NOW()
    WHERE hp.discharge_date IS NULL
      AND hp.expected_recovery_date <= NOW();
    GET DIAGNOSTICS v_discharged = ROW_COUNT;

    UPDATE public.player_cards pc
    SET injury_tier = NULL,
        injury_started_at = NULL,
        injury_recovery_days = 0,
        in_hospital = FALSE,
        fatigue = LEAST(100, fatigue + 25)
    WHERE pc.id IN (
        SELECT player_card_id FROM public.hospital_patients
        WHERE discharge_date IS NOT NULL
          AND discharge_date > NOW() - INTERVAL '1 minute'
    )
    AND pc.in_hospital = TRUE;

    UPDATE public.player_cards
    SET injury_recovery_days = GREATEST(0, injury_recovery_days - 1)
    WHERE injury_tier IS NOT NULL
      AND in_hospital = FALSE
      AND COALESCE(is_retired, FALSE) = FALSE;
    GET DIAGNOSTICS v_untreated = ROW_COUNT;

    UPDATE public.player_cards
    SET injury_tier = NULL,
        injury_started_at = NULL,
        injury_recovery_days = 0
    WHERE injury_tier IS NOT NULL
      AND in_hospital = FALSE
      AND injury_recovery_days <= 0;

    RETURN jsonb_build_object(
        'fatigue_updated', v_fatigue_n,
        'discharged', v_discharged,
        'untreated_decremented', v_untreated,
        'passive_mode', 'intensity_tier_tg2'
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_daily_recovery()
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- process_post_match_injuries — tier × severity ÷ hospital
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
    v_intensity INTEGER;
    v_max_beds INTEGER;
    v_current_beds INTEGER;
    v_base_days INTEGER;
    v_recovery_days INTEGER;
    v_admitted JSONB := '[]'::JSONB;
    v_overflow JSONB := '[]'::JSONB;
BEGIN
    SELECT COALESCE(hospital_level, 0), COALESCE(intensity_tier, 1)
    INTO v_hospital, v_intensity
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

        v_base_days := GREATEST(
            1,
            CEIL(public.intensity_untreated_base_days(v_tier, v_intensity))::INTEGER
        );
        v_recovery_days := public.intensity_recovery_days(v_tier, v_intensity, v_hospital);

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

GRANT ALL PRIVILEGES ON FUNCTION public.process_post_match_injuries(BIGINT, JSONB)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- admit_to_hospital
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
    v_intensity INTEGER;
    v_max_beds INTEGER;
    v_current_beds INTEGER;
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

    SELECT COALESCE(hospital_level, 0), COALESCE(intensity_tier, 1)
    INTO v_hospital, v_intensity
    FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;

    v_max_beds := v_hospital + 1;
    SELECT COUNT(*)::INTEGER INTO v_current_beds
    FROM public.hospital_patients
    WHERE owner_id = p_owner_id AND discharge_date IS NULL;

    IF v_current_beds >= v_max_beds THEN
        RAISE EXCEPTION 'Hospital beds full';
    END IF;

    v_recovery_days := public.intensity_recovery_days(v_tier, v_intensity, v_hospital);

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

GRANT ALL PRIVILEGES ON FUNCTION public.admit_to_hospital(BIGINT, UUID)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- backfill_tier_fatigue_rebalance
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.backfill_tier_fatigue_rebalance()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    r RECORD;
    v_intensity INTEGER;
    v_hospital INTEGER;
    v_new_total INTEGER;
    v_candidate TIMESTAMPTZ;
    v_final_eta TIMESTAMPTZ;
    v_remain_days INTEGER;
    v_elapsed NUMERIC;
    v_base NUMERIC;
    v_remain INTEGER;
    v_final_days INTEGER;
    v_hosp_shortened INTEGER := 0;
    v_hosp_unchanged INTEGER := 0;
    v_hosp_early INTEGER := 0;
    v_ov_shortened INTEGER := 0;
    v_ov_cleared INTEGER := 0;
    v_fatigue_floored INTEGER := 0;
    v_skipped INTEGER := 0;
    v_early JSONB := '[]'::JSONB;
BEGIN
    FOR r IN
        SELECT
            hp.id AS stay_id,
            hp.owner_id,
            hp.player_card_id,
            hp.injury_tier,
            hp.admission_date,
            hp.expected_recovery_date,
            COALESCE(p.hospital_level, 0) AS hospital_level,
            COALESCE(p.intensity_tier, 1) AS intensity_tier,
            pc.name AS card_name,
            pc.is_retired
        FROM public.hospital_patients hp
        JOIN public.players p ON p.discord_id = hp.owner_id
        LEFT JOIN public.player_cards pc ON pc.id = hp.player_card_id
        WHERE hp.discharge_date IS NULL
    LOOP
        IF r.player_card_id IS NULL OR COALESCE(r.is_retired, FALSE) THEN
            v_skipped := v_skipped + 1;
            CONTINUE;
        END IF;

        v_intensity := GREATEST(1, LEAST(3, r.intensity_tier));
        v_hospital := GREATEST(0, r.hospital_level);
        v_new_total := public.intensity_recovery_days(r.injury_tier, v_intensity, v_hospital);
        v_candidate := r.admission_date + (v_new_total || ' days')::INTERVAL;
        v_final_eta := LEAST(r.expected_recovery_date, v_candidate);

        IF NOW() >= v_final_eta THEN
            UPDATE public.hospital_patients
            SET discharge_date = NOW()
            WHERE id = r.stay_id AND discharge_date IS NULL;

            UPDATE public.player_cards
            SET injury_tier = NULL,
                injury_started_at = NULL,
                injury_recovery_days = 0,
                in_hospital = FALSE,
                fatigue = LEAST(100, fatigue + 25)
            WHERE id = r.player_card_id;

            v_hosp_early := v_hosp_early + 1;
            v_early := v_early || jsonb_build_array(jsonb_build_object(
                'owner_id', r.owner_id,
                'player_card_id', r.player_card_id,
                'name', COALESCE(r.card_name, 'Player'),
                'tier', r.injury_tier
            ));
        ELSIF v_final_eta < r.expected_recovery_date THEN
            UPDATE public.hospital_patients
            SET expected_recovery_date = v_final_eta
            WHERE id = r.stay_id AND discharge_date IS NULL;

            v_remain_days := GREATEST(
                1,
                CEIL(EXTRACT(EPOCH FROM (v_final_eta - NOW())) / 86400.0)::INTEGER
            );
            UPDATE public.player_cards
            SET injury_recovery_days = v_remain_days,
                in_hospital = TRUE
            WHERE id = r.player_card_id;

            v_hosp_shortened := v_hosp_shortened + 1;
        ELSE
            v_hosp_unchanged := v_hosp_unchanged + 1;
        END IF;
    END LOOP;

    FOR r IN
        SELECT
            pc.id AS player_card_id,
            pc.owner_id,
            pc.injury_tier,
            pc.injury_started_at,
            pc.injury_recovery_days,
            pc.name AS card_name,
            COALESCE(p.intensity_tier, 1) AS intensity_tier
        FROM public.player_cards pc
        JOIN public.players p ON p.discord_id = pc.owner_id
        WHERE pc.injury_tier IS NOT NULL
          AND pc.in_hospital = FALSE
          AND COALESCE(pc.is_retired, FALSE) = FALSE
    LOOP
        v_intensity := GREATEST(1, LEAST(3, r.intensity_tier));
        v_base := public.intensity_untreated_base_days(r.injury_tier, v_intensity);
        v_elapsed := EXTRACT(
            EPOCH FROM (NOW() - COALESCE(r.injury_started_at, NOW()))
        ) / 86400.0;
        v_remain := GREATEST(0, CEIL(v_base - v_elapsed)::INTEGER);
        v_final_days := LEAST(GREATEST(0, r.injury_recovery_days), v_remain);

        IF v_final_days = 0 THEN
            UPDATE public.player_cards
            SET injury_tier = NULL,
                injury_started_at = NULL,
                injury_recovery_days = 0,
                in_hospital = FALSE
            WHERE id = r.player_card_id;
            v_ov_cleared := v_ov_cleared + 1;
            v_early := v_early || jsonb_build_array(jsonb_build_object(
                'owner_id', r.owner_id,
                'player_card_id', r.player_card_id,
                'name', COALESCE(r.card_name, 'Player'),
                'tier', r.injury_tier,
                'overflow', TRUE
            ));
        ELSIF v_final_days < r.injury_recovery_days THEN
            UPDATE public.player_cards
            SET injury_recovery_days = v_final_days
            WHERE id = r.player_card_id;
            v_ov_shortened := v_ov_shortened + 1;
        END IF;
    END LOOP;

    UPDATE public.player_cards
    SET fatigue = GREATEST(fatigue, 50)
    WHERE injury_tier IS NULL
      AND COALESCE(in_hospital, FALSE) = FALSE
      AND COALESCE(is_retired, FALSE) = FALSE
      AND fatigue < 50;
    GET DIAGNOSTICS v_fatigue_floored = ROW_COUNT;

    RETURN jsonb_build_object(
        'hospital_shortened', v_hosp_shortened,
        'hospital_unchanged', v_hosp_unchanged,
        'hospital_early_discharged', v_hosp_early,
        'overflow_shortened', v_ov_shortened,
        'overflow_cleared', v_ov_cleared,
        'fatigue_floored', v_fatigue_floored,
        'skipped', v_skipped,
        'early_discharged', v_early
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.backfill_tier_fatigue_rebalance()
    TO anon, authenticated, service_role;

GRANT ALL PRIVILEGES ON FUNCTION public.intensity_recovery_days(INTEGER, INTEGER, INTEGER)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.intensity_untreated_base_days(INTEGER, INTEGER)
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'players' AND column_name = 'intensity_tier'
    ) THEN
        RAISE EXCEPTION 'Migration 061 guard failed — players.intensity_tier missing';
    END IF;
    IF to_regprocedure('public.backfill_tier_fatigue_rebalance()') IS NULL THEN
        RAISE EXCEPTION 'Migration 061 guard failed — backfill_tier_fatigue_rebalance missing';
    END IF;
    IF to_regprocedure('public.intensity_recovery_days(integer,integer,integer)') IS NULL THEN
        RAISE EXCEPTION 'Migration 061 guard failed — intensity_recovery_days missing';
    END IF;
END $$;

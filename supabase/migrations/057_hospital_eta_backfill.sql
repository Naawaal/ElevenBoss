-- 057: One-time fair recalculation of open hospital / overflow injury clocks (012).
-- Prerequisite: 056 (injury bases 1/4/7) applied.
-- Idempotent: candidate ETA = admission + new_total; LEAST with current; never lengthen.

CREATE OR REPLACE FUNCTION public.backfill_injury_eta_fairness()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    r RECORD;
    v_base INTEGER;
    v_hospital INTEGER;
    v_new_total INTEGER;
    v_candidate TIMESTAMPTZ;
    v_final_eta TIMESTAMPTZ;
    v_remain_days INTEGER;
    v_elapsed NUMERIC;
    v_remain INTEGER;
    v_final_days INTEGER;
    v_hosp_shortened INTEGER := 0;
    v_hosp_unchanged INTEGER := 0;
    v_hosp_early INTEGER := 0;
    v_ov_shortened INTEGER := 0;
    v_ov_cleared INTEGER := 0;
    v_skipped INTEGER := 0;
    v_early JSONB := '[]'::JSONB;
BEGIN
    -- Active hospital stays
    FOR r IN
        SELECT
            hp.id AS stay_id,
            hp.owner_id,
            hp.player_card_id,
            hp.injury_tier,
            hp.admission_date,
            hp.expected_recovery_date,
            COALESCE(p.hospital_level, 0) AS hospital_level,
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

        v_base := CASE r.injury_tier WHEN 1 THEN 1 WHEN 2 THEN 4 ELSE 7 END;
        v_hospital := GREATEST(0, r.hospital_level);
        v_new_total := CEIL(v_base::NUMERIC / (1 + 0.2 * v_hospital))::INTEGER;
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

    -- Overflow / untreated (not in hospital)
    FOR r IN
        SELECT
            pc.id AS player_card_id,
            pc.owner_id,
            pc.injury_tier,
            pc.injury_started_at,
            pc.injury_recovery_days,
            pc.name AS card_name
        FROM public.player_cards pc
        WHERE pc.injury_tier IS NOT NULL
          AND pc.in_hospital = FALSE
          AND COALESCE(pc.is_retired, FALSE) = FALSE
    LOOP
        v_base := CASE r.injury_tier WHEN 1 THEN 1 WHEN 2 THEN 4 ELSE 7 END;
        v_elapsed := EXTRACT(
            EPOCH FROM (NOW() - COALESCE(r.injury_started_at, NOW()))
        ) / 86400.0;
        v_remain := GREATEST(0, CEIL(v_base::NUMERIC - v_elapsed)::INTEGER);
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

    RETURN jsonb_build_object(
        'hospital_shortened', v_hosp_shortened,
        'hospital_unchanged', v_hosp_unchanged,
        'hospital_early_discharged', v_hosp_early,
        'overflow_shortened', v_ov_shortened,
        'overflow_cleared', v_ov_cleared,
        'skipped', v_skipped,
        'early_discharged', v_early
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.backfill_injury_eta_fairness()
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.backfill_injury_eta_fairness()') IS NULL THEN
        RAISE EXCEPTION 'Migration 057 guard failed — backfill_injury_eta_fairness missing';
    END IF;
END $$;

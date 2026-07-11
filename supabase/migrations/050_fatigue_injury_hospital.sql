-- 050: Player fatigue, injury, hospital facility (Phases 1–2)
-- Fatigue on player_cards; hospital_level on players; hospital_patients + RPCs.
-- Hospital costs: 1500/4000/10000/25000/60000; injury soft-cap A+C enforced in Python.

ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS fatigue INTEGER NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS injury_tier INTEGER,
    ADD COLUMN IF NOT EXISTS injury_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS injury_recovery_days INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS in_hospital BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_fatigue_check,
    DROP CONSTRAINT IF EXISTS player_cards_injury_tier_check;

ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_fatigue_check CHECK (fatigue BETWEEN 0 AND 100),
    ADD CONSTRAINT player_cards_injury_tier_check
        CHECK (injury_tier IS NULL OR injury_tier BETWEEN 1 AND 3);

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS hospital_level INTEGER NOT NULL DEFAULT 0;

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_hospital_level_check;

ALTER TABLE public.players
    ADD CONSTRAINT players_hospital_level_check CHECK (hospital_level BETWEEN 0 AND 5);

CREATE TABLE IF NOT EXISTS public.hospital_patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    player_card_id UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    injury_tier INTEGER NOT NULL CHECK (injury_tier BETWEEN 1 AND 3),
    admission_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expected_recovery_date TIMESTAMPTZ NOT NULL,
    discharge_date TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS hospital_patients_one_active
    ON public.hospital_patients (player_card_id)
    WHERE discharge_date IS NULL;

CREATE INDEX IF NOT EXISTS idx_hospital_patients_owner_active
    ON public.hospital_patients (owner_id)
    WHERE discharge_date IS NULL;

ALTER TABLE public.hospital_patients ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hospital_patients_select ON public.hospital_patients;
DROP POLICY IF EXISTS hospital_patients_insert ON public.hospital_patients;
DROP POLICY IF EXISTS hospital_patients_update ON public.hospital_patients;

CREATE POLICY hospital_patients_select ON public.hospital_patients
    FOR SELECT TO anon, authenticated, service_role USING (true);

CREATE POLICY hospital_patients_insert ON public.hospital_patients
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

CREATE POLICY hospital_patients_update ON public.hospital_patients
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE public.hospital_patients TO anon, authenticated, service_role;

INSERT INTO public.game_config (key, value_json) VALUES
    ('hospital_upgrade_costs', '[1500, 4000, 10000, 25000, 60000]'),
    ('fatigue_base_drain', '22'),
    ('fatigue_passive_per_day', '20'),
    ('fatigue_hospital_per_day', '45'),
    ('fatigue_bench_per_match', '15'),
    ('hospital_upgrade_min_matches', '{"2": 5, "4": 20}')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- apply_match_fatigue
-- ---------------------------------------------------------------------------
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
    v_bench_amt := public.get_game_config_int('fatigue_bench_per_match', 15)::INTEGER;

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

-- ---------------------------------------------------------------------------
-- process_post_match_injuries
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

        v_base_days := CASE v_tier WHEN 1 THEN 3 WHEN 2 THEN 8 ELSE 20 END;
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
-- process_daily_recovery
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_daily_recovery()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_passive INTEGER;
    v_hosp INTEGER;
    v_fatigue_n INTEGER;
    v_discharged INTEGER;
    v_untreated INTEGER;
BEGIN
    v_passive := public.get_game_config_int('fatigue_passive_per_day', 20)::INTEGER;
    v_hosp := public.get_game_config_int('fatigue_hospital_per_day', 45)::INTEGER;

    UPDATE public.player_cards
    SET fatigue = LEAST(100, fatigue + CASE WHEN in_hospital THEN v_hosp ELSE v_passive END)
    WHERE fatigue < 100 AND COALESCE(is_retired, FALSE) = FALSE;
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
        'untreated_decremented', v_untreated
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- admit / discharge
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

    v_base_days := CASE v_tier WHEN 1 THEN 3 WHEN 2 THEN 8 ELSE 20 END;
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

CREATE OR REPLACE FUNCTION public.discharge_from_hospital(
    p_owner_id BIGINT,
    p_player_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_tier INTEGER;
    v_days INTEGER;
BEGIN
    UPDATE public.hospital_patients
    SET discharge_date = NOW()
    WHERE owner_id = p_owner_id
      AND player_card_id = p_player_card_id
      AND discharge_date IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No active hospital admission';
    END IF;

    SELECT injury_tier, injury_recovery_days INTO v_tier, v_days
    FROM public.player_cards
    WHERE id = p_player_card_id AND owner_id = p_owner_id;

    -- Untreated path: keep injury, leave hospital (1.0x remaining days)
    UPDATE public.player_cards
    SET in_hospital = FALSE,
        injury_recovery_days = GREATEST(1, COALESCE(v_days, 3))
    WHERE id = p_player_card_id;

    RETURN jsonb_build_object(
        'player_card_id', p_player_card_id,
        'still_injured', TRUE,
        'tier', v_tier,
        'recovery_days', GREATEST(1, COALESCE(v_days, 3))
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- upgrade_club_facility — add hospital
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.upgrade_club_facility(
    p_owner_id BIGINT,
    p_facility_key TEXT,
    p_expected_cost BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_coins BIGINT;
    v_matches INTEGER;
    v_youth INTEGER;
    v_training INTEGER;
    v_hospital INTEGER;
    v_current INTEGER;
    v_next INTEGER;
    v_cost BIGINT;
    v_last_upgrade TIMESTAMPTZ;
    v_cap_days INTEGER;
    v_min_json JSONB;
    v_min_matches INTEGER;
    v_costs JSONB;
BEGIN
    IF p_facility_key NOT IN ('youth_academy', 'training_ground', 'hospital') THEN
        RAISE EXCEPTION 'Unknown facility: %', p_facility_key;
    END IF;

    SELECT coins, matches_played, youth_academy_level, training_ground_level,
           COALESCE(hospital_level, 0), facility_last_upgrade_at
    INTO v_coins, v_matches, v_youth, v_training, v_hospital, v_last_upgrade
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Manager not found';
    END IF;

    IF p_facility_key = 'hospital' THEN
        v_current := v_hospital;
        IF v_current >= 5 THEN
            RAISE EXCEPTION 'Facility already at maximum level';
        END IF;
        v_next := v_current + 1;
        v_costs := public.get_game_config('hospital_upgrade_costs');
        v_cost := COALESCE((v_costs ->> (v_current))::BIGINT, NULL);
        v_min_json := public.get_game_config('hospital_upgrade_min_matches');
    ELSE
        v_current := CASE p_facility_key
            WHEN 'youth_academy' THEN COALESCE(v_youth, 1)
            ELSE COALESCE(v_training, 1)
        END;
        IF v_current >= 5 THEN
            RAISE EXCEPTION 'Facility already at maximum level';
        END IF;
        v_next := v_current + 1;
        v_cost := public.facility_upgrade_cost_for_level(v_current);
        v_min_json := public.get_game_config('facility_upgrade_min_matches');
    END IF;

    IF v_cost IS NULL THEN
        RAISE EXCEPTION 'Invalid facility level';
    END IF;

    IF p_expected_cost IS DISTINCT FROM v_cost THEN
        RAISE EXCEPTION 'Upgrade cost mismatch (expected % coins)', v_cost;
    END IF;

    v_cap_days := public.get_game_config_int('facility_upgrade_weekly_cap_days', 7)::INTEGER;
    IF v_last_upgrade IS NOT NULL AND v_last_upgrade > NOW() - (v_cap_days || ' days')::INTERVAL THEN
        RAISE EXCEPTION 'Facility upgrade on cooldown (1 per UTC week)';
    END IF;

    v_min_matches := COALESCE((v_min_json ->> v_next::TEXT)::INTEGER, 0);
    IF v_min_matches > 0 AND COALESCE(v_matches, 0) < v_min_matches THEN
        RAISE EXCEPTION 'Requires at least % career matches to reach level %', v_min_matches, v_next;
    END IF;

    IF v_coins < v_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    PERFORM public.apply_club_economy(
        p_owner_id,
        -v_cost,
        0,
        'facility_upgrade',
        'facility:' || p_facility_key || ':' || p_owner_id::TEXT || ':L' || v_next::TEXT,
        jsonb_build_object('facility', p_facility_key, 'from_level', v_current, 'to_level', v_next, 'cost', v_cost)
    );

    IF p_facility_key = 'youth_academy' THEN
        UPDATE public.players
        SET youth_academy_level = v_next, facility_last_upgrade_at = NOW()
        WHERE discord_id = p_owner_id;
    ELSIF p_facility_key = 'training_ground' THEN
        UPDATE public.players
        SET training_ground_level = v_next, facility_last_upgrade_at = NOW()
        WHERE discord_id = p_owner_id;
    ELSE
        UPDATE public.players
        SET hospital_level = v_next, facility_last_upgrade_at = NOW()
        WHERE discord_id = p_owner_id;
    END IF;

    RETURN jsonb_build_object(
        'facility', p_facility_key,
        'new_level', v_next,
        'coins_spent', v_cost,
        'youth_academy_level', CASE WHEN p_facility_key = 'youth_academy' THEN v_next ELSE v_youth END,
        'training_ground_level', CASE WHEN p_facility_key = 'training_ground' THEN v_next ELSE v_training END,
        'hospital_level', CASE WHEN p_facility_key = 'hospital' THEN v_next ELSE v_hospital END
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.apply_match_fatigue(BIGINT, JSONB, UUID[]) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_post_match_injuries(BIGINT, JSONB) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_daily_recovery() TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.admit_to_hospital(BIGINT, UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.discharge_from_hospital(BIGINT, UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.upgrade_club_facility(BIGINT, TEXT, BIGINT) TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.player_cards.fatigue'),
            ('column:public.player_cards.injury_tier'),
            ('column:public.players.hospital_level'),
            ('table:public.hospital_patients'),
            ('function:apply_match_fatigue'),
            ('function:process_post_match_injuries'),
            ('function:process_daily_recovery'),
            ('function:admit_to_hospital'),
            ('function:discharge_from_hospital'),
            ('policy:public.hospital_patients.hospital_patients_select')
    ) AS req(obj)
    WHERE NOT (
        (
            req.obj LIKE 'column:%'
            AND EXISTS (
                SELECT 1 FROM information_schema.columns c
                WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (
            req.obj LIKE 'table:%'
            AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL
        )
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'apply_match_fatigue' THEN to_regprocedure('public.apply_match_fatigue(bigint,jsonb,uuid[])')
                WHEN 'process_post_match_injuries' THEN to_regprocedure('public.process_post_match_injuries(bigint,jsonb)')
                WHEN 'process_daily_recovery' THEN to_regprocedure('public.process_daily_recovery()')
                WHEN 'admit_to_hospital' THEN to_regprocedure('public.admit_to_hospital(bigint,uuid)')
                WHEN 'discharge_from_hospital' THEN to_regprocedure('public.discharge_from_hospital(bigint,uuid)')
                ELSE NULL
            END IS NOT NULL
        )
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

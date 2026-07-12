-- 054: Active fatigue recovery — Recovery Session RPC + TG-scaled daily passive.
-- No new tables. Extends US-39 / specs/009-fatigue-recovery.

INSERT INTO public.game_config (key, value_json) VALUES
    ('fatigue_recovery_session', '40'),
    ('fatigue_recovery_energy', '10'),
    ('fatigue_passive_base', '15'),
    ('fatigue_passive_tg_per_level', '5')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- process_recovery_session — instant Development recovery (0 XP, 0 coins)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_recovery_session(
    p_owner_id BIGINT,
    p_player_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_energy INTEGER;
    v_daily INTEGER;
    v_reset DATE;
    v_daily_limit INTEGER := 20;
    v_player_drill_count INTEGER;
    v_player_drill_cap CONSTANT INTEGER := 5;
    v_recovery_energy INTEGER;
    v_recovery_amount INTEGER;
    v_fatigue INTEGER;
    v_old_fatigue INTEGER;
    v_injury INTEGER;
    v_in_hospital BOOLEAN;
    v_econ JSONB;
    v_gained INTEGER;
BEGIN
    PERFORM public.sync_action_energy(p_owner_id);

    SELECT action_energy, daily_drill_count, daily_drill_reset_at
    INTO v_energy, v_daily, v_reset
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    PERFORM public.assert_not_in_match(p_owner_id);

    IF v_reset IS NULL OR v_reset < CURRENT_DATE THEN
        v_daily := 0;
        v_reset := CURRENT_DATE;
    END IF;

    IF v_daily >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily drill limit reached';
    END IF;

    SELECT fatigue, injury_tier, COALESCE(in_hospital, FALSE)
    INTO v_fatigue, v_injury, v_in_hospital
    FROM public.player_cards
    WHERE id = p_player_card_id
      AND owner_id = p_owner_id
      AND COALESCE(is_retired, FALSE) = FALSE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF v_injury IS NOT NULL OR v_in_hospital THEN
        RAISE EXCEPTION 'Player is injured — use Hospital';
    END IF;

    IF v_fatigue >= 100 THEN
        RAISE EXCEPTION 'Player is already fully rested';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_player_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Player is in an active evolution track';
    END IF;

    INSERT INTO public.player_drill_daily_log (card_id, drill_date, count)
    VALUES (p_player_card_id, CURRENT_DATE, 1)
    ON CONFLICT (card_id, drill_date)
    DO UPDATE SET count = player_drill_daily_log.count + 1
    RETURNING count INTO v_player_drill_count;

    IF v_player_drill_count > v_player_drill_cap THEN
        RAISE EXCEPTION 'Daily drill limit reached for this player (max % per day)', v_player_drill_cap;
    END IF;

    v_recovery_energy := public.get_game_config_int('fatigue_recovery_energy', 10)::INTEGER;
    v_recovery_amount := public.get_game_config_int('fatigue_recovery_session', 40)::INTEGER;

    IF v_energy < v_recovery_energy THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    v_econ := public.apply_club_economy(
        p_owner_id,
        0,
        -v_recovery_energy,
        'recovery_session',
        NULL,
        jsonb_build_object(
            'card_id', p_player_card_id,
            'fatigue_before', v_fatigue,
            'recovery_amount', v_recovery_amount
        )
    );

    UPDATE public.players
    SET daily_drill_count = v_daily + 1,
        daily_drill_reset_at = v_reset
    WHERE discord_id = p_owner_id;

    v_old_fatigue := v_fatigue;
    v_fatigue := LEAST(100, v_fatigue + v_recovery_amount);
    v_gained := v_fatigue - v_old_fatigue;

    UPDATE public.player_cards
    SET fatigue = v_fatigue
    WHERE id = p_player_card_id;

    RETURN jsonb_build_object(
        'fatigue_gained', v_gained,
        'new_fatigue', v_fatigue,
        'energy_spent', v_recovery_energy,
        'coins_spent', 0,
        'xp_gained', 0,
        'economy', v_econ
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_recovery_session(BIGINT, UUID)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- process_daily_recovery — TG-scaled non-hospital passive
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_daily_recovery()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_base INTEGER;
    v_tg_bonus INTEGER;
    v_hosp INTEGER;
    v_fatigue_n INTEGER;
    v_discharged INTEGER;
    v_untreated INTEGER;
BEGIN
    v_base := public.get_game_config_int('fatigue_passive_base', 15)::INTEGER;
    v_tg_bonus := public.get_game_config_int('fatigue_passive_tg_per_level', 5)::INTEGER;
    v_hosp := public.get_game_config_int('fatigue_hospital_per_day', 45)::INTEGER;

    UPDATE public.player_cards pc
    SET fatigue = LEAST(
        100,
        pc.fatigue + CASE
            WHEN pc.in_hospital THEN v_hosp
            ELSE v_base + COALESCE(p.training_ground_level, 1) * v_tg_bonus
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
        'passive_mode', 'tg_scaled'
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_daily_recovery()
    TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('function:process_recovery_session'),
            ('function:process_daily_recovery')
    ) AS req(obj)
    WHERE NOT (
        (req.obj = 'function:process_recovery_session'
            AND to_regprocedure('public.process_recovery_session(bigint,uuid)') IS NOT NULL)
        OR (req.obj = 'function:process_daily_recovery'
            AND to_regprocedure('public.process_daily_recovery()') IS NOT NULL)
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 054 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

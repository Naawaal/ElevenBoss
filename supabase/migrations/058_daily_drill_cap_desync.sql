-- 058: Daily drill cap desync — null-safe soft-reset + repair from today's log.
-- Spec: specs/013-daily-drill-reset/

CREATE OR REPLACE FUNCTION public.process_stat_drill(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_drill_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_coins BIGINT;
    v_energy INTEGER;
    v_daily INTEGER;
    v_reset DATE;
    v_tg_level INTEGER;
    v_ovr INTEGER;
    v_card_level INTEGER;
    v_dob DATE;
    v_age INTEGER;
    v_cost BIGINT;
    v_daily_limit INTEGER := 20;
    v_drill_energy INTEGER;
    v_drill_min_level INTEGER := 1;
    v_drill_xp_base INTEGER;
    v_drill_flat BIGINT;
    v_drill_ovr_mult INTEGER;
    v_advanced_min INTEGER;
    v_xp_gain INTEGER;
    v_xp_result JSONB;
    v_player_drill_count INTEGER;
    v_player_drill_cap CONSTANT INTEGER := 5;
    v_econ JSONB;
BEGIN
    PERFORM public.sync_action_energy(p_owner_id);

    SELECT coins, action_energy, daily_drill_count, daily_drill_reset_at,
           COALESCE(training_ground_level, 1)
    INTO v_coins, v_energy, v_daily, v_reset, v_tg_level
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    PERFORM public.assert_not_in_match(p_owner_id);

    -- Null-safe soft-reset (parity with process_recovery_session)
    IF v_reset IS NULL OR v_reset < CURRENT_DATE THEN
        v_daily := 0;
        v_reset := CURRENT_DATE;
    END IF;

    IF v_daily >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily drill limit reached';
    END IF;

    IF p_drill_id NOT IN (
        'pac_sprint', 'sho_finishing', 'pas_distribution',
        'dri_dribble', 'def_tackling', 'phy_strength'
    ) THEN
        RAISE EXCEPTION 'Unknown drill type';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_owner_id AND COALESCE(is_retired, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Player is in an active evolution track';
    END IF;

    SELECT overall, level, date_of_birth
    INTO v_ovr, v_card_level, v_dob
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    v_age := public.card_age_from_dob(v_dob);

    v_advanced_min := public.get_game_config_int('drill_advanced_min_level', 10)::INTEGER;

    IF v_card_level >= v_advanced_min THEN
        v_drill_flat := public.get_game_config_int('drill_advanced_flat', 300);
        v_drill_ovr_mult := public.get_game_config_int('drill_advanced_ovr_mult', 3)::INTEGER;
        v_drill_energy := public.get_game_config_int('drill_advanced_energy', 15)::INTEGER;
        v_drill_xp_base := public.get_game_config_int('drill_advanced_xp', 80)::INTEGER;
        v_drill_min_level := v_advanced_min;
    ELSE
        v_drill_flat := public.get_game_config_int('drill_basic_flat', 100);
        v_drill_ovr_mult := public.get_game_config_int('drill_basic_ovr_mult', 2)::INTEGER;
        v_drill_energy := public.get_game_config_int('drill_basic_energy', 10)::INTEGER;
        v_drill_xp_base := public.get_game_config_int('drill_basic_xp', 30)::INTEGER;
    END IF;

    IF v_card_level < v_drill_min_level THEN
        RAISE EXCEPTION 'Player level too low for this drill (requires level %)', v_drill_min_level;
    END IF;

    INSERT INTO public.player_drill_daily_log (card_id, drill_date, count)
    VALUES (p_card_id, CURRENT_DATE, 1)
    ON CONFLICT (card_id, drill_date)
    DO UPDATE SET count = player_drill_daily_log.count + 1
    RETURNING count INTO v_player_drill_count;

    IF v_player_drill_count > v_player_drill_cap THEN
        RAISE EXCEPTION 'Daily drill limit reached for this player (max % per day)', v_player_drill_cap;
    END IF;

    IF v_energy < v_drill_energy THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    v_cost := (v_drill_flat + v_drill_ovr_mult * v_ovr)::BIGINT;
    IF v_coins < v_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    v_xp_gain := GREATEST(
        1,
        floor(
            v_drill_xp_base::NUMERIC
            / (1.0 + 0.05 * GREATEST(0, v_card_level - 1))
        )::INTEGER
    );

    v_xp_gain := GREATEST(
        1,
        floor(v_xp_gain * public.card_xp_age_multiplier(v_age))::INTEGER
            + public.training_ground_xp_bonus(v_tg_level)
    );

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_cost,
        -v_drill_energy,
        'stat_drill_' || p_drill_id,
        NULL,
        jsonb_build_object(
            'card_id', p_card_id,
            'drill_id', p_drill_id,
            'cost', v_cost,
            'age', v_age,
            'training_ground_level', v_tg_level
        )
    );

    UPDATE public.players
    SET daily_drill_count = v_daily + 1,
        daily_drill_reset_at = v_reset
    WHERE discord_id = p_owner_id;

    v_xp_result := public.apply_card_xp(p_card_id, v_xp_gain, 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'xp_gain', v_xp_gain,
        'cost', v_cost,
        'daily_drill_count', v_daily + 1,
        'daily_drill_limit', v_daily_limit,
        'training_ground_bonus', public.training_ground_xp_bonus(v_tg_level),
        'economy', v_econ,
        'progression', v_xp_result
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;

-- Reconcile club counters from today's per-card drill log (idempotent).
CREATE OR REPLACE FUNCTION public.repair_daily_drill_counts()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    r RECORD;
    v_log_sum INTEGER;
    v_new INTEGER;
    v_checked INTEGER := 0;
    v_updated INTEGER := 0;
BEGIN
    FOR r IN
        SELECT discord_id, daily_drill_count, daily_drill_reset_at
        FROM public.players
    LOOP
        v_checked := v_checked + 1;

        SELECT LEAST(
            20,
            COALESCE(SUM(l.count), 0)::INTEGER
        )
        INTO v_log_sum
        FROM public.player_drill_daily_log l
        JOIN public.player_cards c ON c.id = l.card_id
        WHERE c.owner_id = r.discord_id
          AND l.drill_date = CURRENT_DATE;

        v_new := COALESCE(v_log_sum, 0);

        IF r.daily_drill_reset_at IS NULL
           OR r.daily_drill_reset_at < CURRENT_DATE
           OR COALESCE(r.daily_drill_count, 0) IS DISTINCT FROM v_new
        THEN
            UPDATE public.players
            SET daily_drill_count = v_new,
                daily_drill_reset_at = CURRENT_DATE
            WHERE discord_id = r.discord_id
              AND (
                  daily_drill_reset_at IS DISTINCT FROM CURRENT_DATE
                  OR daily_drill_count IS DISTINCT FROM v_new
              );
            IF FOUND THEN
                v_updated := v_updated + 1;
            END IF;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'checked', v_checked,
        'updated', v_updated
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.repair_daily_drill_counts()
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.process_stat_drill(bigint,uuid,text)') IS NULL THEN
        RAISE EXCEPTION 'Migration 058 guard failed — process_stat_drill missing';
    END IF;
    IF to_regprocedure('public.repair_daily_drill_counts()') IS NULL THEN
        RAISE EXCEPTION 'Migration 058 guard failed — repair_daily_drill_counts missing';
    END IF;
END $$;

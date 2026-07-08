-- 043: Club facilities — Youth Academy + Training Ground (Phase C)

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS youth_academy_level INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS training_ground_level INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS facility_last_upgrade_at TIMESTAMPTZ;

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_youth_academy_level_check,
    DROP CONSTRAINT IF EXISTS players_training_ground_level_check;

ALTER TABLE public.players
    ADD CONSTRAINT players_youth_academy_level_check
        CHECK (youth_academy_level BETWEEN 1 AND 5),
    ADD CONSTRAINT players_training_ground_level_check
        CHECK (training_ground_level BETWEEN 1 AND 5);

INSERT INTO public.game_config (key, value_json) VALUES
    ('facility_upgrade_costs', '[750, 2000, 5000, 12000]'),
    ('facility_upgrade_weekly_cap_days', '7'),
    ('facility_upgrade_min_matches', '{"2": 5, "4": 20}')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.training_ground_xp_bonus(p_level INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT GREATEST(0, LEAST(4, COALESCE(p_level, 1) - 1));
$$;

CREATE OR REPLACE FUNCTION public.facility_upgrade_cost_for_level(p_current_level INTEGER)
RETURNS BIGINT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_costs JSONB;
BEGIN
    IF p_current_level IS NULL OR p_current_level < 1 OR p_current_level >= 5 THEN
        RETURN NULL;
    END IF;
    v_costs := public.get_game_config('facility_upgrade_costs');
    RETURN COALESCE((v_costs ->> (p_current_level - 1))::BIGINT, NULL);
END;
$$;

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
    v_current INTEGER;
    v_next INTEGER;
    v_cost BIGINT;
    v_last_upgrade TIMESTAMPTZ;
    v_cap_days INTEGER;
    v_min_json JSONB;
    v_min_matches INTEGER;
    v_col TEXT;
BEGIN
    IF p_facility_key NOT IN ('youth_academy', 'training_ground') THEN
        RAISE EXCEPTION 'Unknown facility: %', p_facility_key;
    END IF;

    SELECT coins, matches_played, youth_academy_level, training_ground_level, facility_last_upgrade_at
    INTO v_coins, v_matches, v_youth, v_training, v_last_upgrade
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Manager not found';
    END IF;

    v_current := CASE p_facility_key
        WHEN 'youth_academy' THEN COALESCE(v_youth, 1)
        ELSE COALESCE(v_training, 1)
    END;

    IF v_current >= 5 THEN
        RAISE EXCEPTION 'Facility already at maximum level';
    END IF;

    v_next := v_current + 1;
    v_cost := public.facility_upgrade_cost_for_level(v_current);
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

    v_min_json := public.get_game_config('facility_upgrade_min_matches');
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
        SET youth_academy_level = v_next,
            facility_last_upgrade_at = NOW()
        WHERE discord_id = p_owner_id;
    ELSE
        UPDATE public.players
        SET training_ground_level = v_next,
            facility_last_upgrade_at = NOW()
        WHERE discord_id = p_owner_id;
    END IF;

    RETURN jsonb_build_object(
        'facility', p_facility_key,
        'new_level', v_next,
        'coins_spent', v_cost,
        'youth_academy_level', CASE WHEN p_facility_key = 'youth_academy' THEN v_next ELSE v_youth END,
        'training_ground_level', CASE WHEN p_facility_key = 'training_ground' THEN v_next ELSE v_training END
    );
END;
$$;

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

    IF v_reset < CURRENT_DATE THEN
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

GRANT ALL PRIVILEGES ON FUNCTION public.training_ground_xp_bonus(INTEGER) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.facility_upgrade_cost_for_level(INTEGER) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.upgrade_club_facility(BIGINT, TEXT, BIGINT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill(BIGINT, UUID, TEXT) TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.players.youth_academy_level'),
            ('column:public.players.training_ground_level'),
            ('column:public.players.facility_last_upgrade_at'),
            ('function:training_ground_xp_bonus'),
            ('function:upgrade_club_facility'),
            ('function:process_stat_drill')
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
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'training_ground_xp_bonus' THEN to_regprocedure('public.training_ground_xp_bonus(integer)')
                WHEN 'upgrade_club_facility' THEN to_regprocedure('public.upgrade_club_facility(bigint,text,bigint)')
                WHEN 'process_stat_drill' THEN to_regprocedure('public.process_stat_drill(bigint,uuid,text)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

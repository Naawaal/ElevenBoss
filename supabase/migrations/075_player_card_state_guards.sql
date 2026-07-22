-- 075_player_card_state_guards.sql
-- US-42.2: shared card-state assert + wire Critical (and soft) gap RPCs.

CREATE OR REPLACE FUNCTION public.card_primary_state(p_card_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_owner BIGINT;
    v_retired BOOLEAN;
    v_hospital BOOLEAN;
    v_academy BOOLEAN;
    v_listed BOOLEAN;
    v_evolving BOOLEAN;
    v_training BOOLEAN;
    v_in_xi BOOLEAN;
BEGIN
    SELECT owner_id,
           COALESCE(is_retired, FALSE),
           COALESCE(in_hospital, FALSE),
           COALESCE(in_academy, FALSE)
    INTO v_owner, v_retired, v_hospital, v_academy
    FROM public.player_cards
    WHERE id = p_card_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF v_retired THEN
        RETURN 'Retired';
    END IF;

    v_listed := EXISTS (
        SELECT 1 FROM public.transfer_listings
        WHERE card_id = p_card_id AND status = 'active'
    );
    IF v_listed THEN
        RETURN 'Listed';
    END IF;

    IF v_hospital THEN
        RETURN 'Hospitalized';
    END IF;

    v_evolving := EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    );
    IF v_evolving THEN
        RETURN 'Evolving';
    END IF;

    v_training := EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    );
    IF v_training THEN
        RETURN 'TrainingBusy';
    END IF;

    IF v_academy THEN
        RETURN 'InAcademy';
    END IF;

    v_in_xi := EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    );
    IF v_in_xi THEN
        RETURN 'InXI';
    END IF;

    RETURN 'RosterFree';
END;
$$;

CREATE OR REPLACE FUNCTION public.assert_card_action_allowed(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_action TEXT
) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
    v_retired BOOLEAN;
    v_hospital BOOLEAN;
    v_academy BOOLEAN;
    v_injury INTEGER;
    v_listed BOOLEAN;
    v_evolving BOOLEAN;
    v_training BOOLEAN;
    v_in_xi BOOLEAN;
    v_busy INT := 0;
    v_primary TEXT;
    v_mutation BOOLEAN;
BEGIN
    IF p_action IS NULL OR btrim(p_action) = '' THEN
        RAISE EXCEPTION 'CARD_STATE: missing action';
    END IF;

    SELECT owner_id,
           COALESCE(is_retired, FALSE),
           COALESCE(in_hospital, FALSE),
           COALESCE(in_academy, FALSE),
           injury_tier
    INTO v_owner, v_retired, v_hospital, v_academy, v_injury
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF v_owner IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    v_listed := EXISTS (
        SELECT 1 FROM public.transfer_listings
        WHERE card_id = p_card_id AND status = 'active'
    );
    v_evolving := EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    );
    v_training := EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    );
    v_in_xi := EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    );

    IF v_retired THEN v_busy := v_busy + 1; END IF;
    IF v_listed THEN v_busy := v_busy + 1; END IF;
    IF v_hospital THEN v_busy := v_busy + 1; END IF;
    IF v_evolving THEN v_busy := v_busy + 1; END IF;
    IF v_training THEN v_busy := v_busy + 1; END IF;
    IF v_academy THEN v_busy := v_busy + 1; END IF;

    IF v_busy > 1 OR (v_busy >= 1 AND v_in_xi) THEN
        RAISE EXCEPTION 'CARD_STATE: state_conflict';
    END IF;

    -- Priority mirrors packages/player_engine/card_state.py
    IF v_retired THEN
        v_primary := 'Retired';
    ELSIF v_listed THEN
        v_primary := 'Listed';
    ELSIF v_hospital THEN
        v_primary := 'Hospitalized';
    ELSIF v_evolving THEN
        v_primary := 'Evolving';
    ELSIF v_training THEN
        v_primary := 'TrainingBusy';
    ELSIF v_academy THEN
        v_primary := 'InAcademy';
    ELSIF v_in_xi THEN
        v_primary := 'InXI';
    ELSE
        v_primary := 'RosterFree';
    END IF;

    v_mutation := p_action IS DISTINCT FROM 'view_profile';
    IF v_mutation THEN
        PERFORM public.assert_not_in_match(p_owner_id);
    END IF;

    -- Matrix Allow sets (spec §B.5)
    IF p_action = 'view_profile' THEN
        RETURN;
    ELSIF p_action = 'assign_xi' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks assign_xi', v_primary;
        END IF;
    ELSIF p_action = 'bench' THEN
        IF v_primary IS DISTINCT FROM 'InXI' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks bench', v_primary;
        END IF;
    ELSIF p_action = 'match_include' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks match_include', v_primary;
        END IF;
    ELSIF p_action = 'drill' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks drill', v_primary;
        END IF;
    ELSIF p_action = 'fusion' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks fusion', v_primary;
        END IF;
    ELSIF p_action = 'allocate' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks allocate', v_primary;
        END IF;
    ELSIF p_action = 'recover_fatigue' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks recover_fatigue', v_primary;
        END IF;
    ELSIF p_action = 'start_evolution' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks start_evolution', v_primary;
        END IF;
    ELSIF p_action IN ('claim_evolution', 'cancel_evolution') THEN
        IF v_primary IS DISTINCT FROM 'Evolving' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    ELSIF p_action = 'admit_hospital' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks admit_hospital', v_primary;
        END IF;
    ELSIF p_action = 'discharge_hospital' THEN
        IF v_primary IS DISTINCT FROM 'Hospitalized' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks discharge_hospital', v_primary;
        END IF;
    ELSIF p_action = 'list_transfer' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks list_transfer', v_primary;
        END IF;
        -- InjuryPlayOn modifier (fatigue alone does NOT block list)
        IF v_injury IS NOT NULL OR v_hospital THEN
            RAISE EXCEPTION 'CARD_STATE: injury blocks list_transfer';
        END IF;
    ELSIF p_action = 'cancel_listing' THEN
        IF v_primary IS DISTINCT FROM 'Listed' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks cancel_listing', v_primary;
        END IF;
    ELSIF p_action = 'agent_sell' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks agent_sell', v_primary;
        END IF;
        IF v_injury IS NOT NULL OR v_hospital THEN
            RAISE EXCEPTION 'CARD_STATE: injury blocks agent_sell';
        END IF;
    ELSIF p_action = 'academy_seat' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks academy_seat', v_primary;
        END IF;
    ELSIF p_action IN ('academy_promote', 'academy_release') THEN
        IF v_primary IS DISTINCT FROM 'InAcademy' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    ELSIF p_action = 'retire' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks retire', v_primary;
        END IF;
    ELSE
        -- Default: only RosterFree / InXI for unknown future mutations
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    END IF;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.card_primary_state(UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.assert_card_action_allowed(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Critical gap wires (from rpc-guard-audit.md)
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
    PERFORM public.assert_card_action_allowed(p_owner_id, p_player_card_id, 'admit_hospital');

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

CREATE OR REPLACE FUNCTION public.swap_squad_players(
    p_discord_id BIGINT,
    p_slot INTEGER,
    p_reserve_card_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_starter_id UUID;
    v_reserve_pos TEXT;
    v_formation TEXT;
    v_required_role TEXT;
BEGIN
    PERFORM public.assert_not_in_match(p_discord_id);
    PERFORM public.assert_card_not_on_transfer_list(p_reserve_card_id);
    PERFORM public.assert_card_action_allowed(p_discord_id, p_reserve_card_id, 'assign_xi');

    IF p_slot < 1 OR p_slot > 11 THEN
        RAISE EXCEPTION 'Invalid squad slot';
    END IF;

    SELECT position INTO v_reserve_pos
    FROM public.player_cards
    WHERE id = p_reserve_card_id AND owner_id = p_discord_id
    FOR UPDATE;

    IF v_reserve_pos IS NULL THEN
        RAISE EXCEPTION 'Reserve player not found or not owned';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE discord_id = p_discord_id AND player_card_id = p_reserve_card_id
    ) THEN
        RAISE EXCEPTION 'Reserve player is already in the starting 11';
    END IF;

    SELECT formation INTO v_formation
    FROM public.squads
    WHERE discord_id = p_discord_id;
    v_required_role := public.formation_slot_role(
        COALESCE(v_formation, '4-4-2'), p_slot
    );
    IF v_reserve_pos != v_required_role THEN
        RAISE EXCEPTION
            'Player position % does not match slot requirement %',
            v_reserve_pos, v_required_role;
    END IF;

    SELECT player_card_id INTO v_starter_id
    FROM public.squad_assignments
    WHERE discord_id = p_discord_id AND position_slot = p_slot
    FOR UPDATE;
    IF v_starter_id IS NULL THEN
        RAISE EXCEPTION 'No starter assigned to that slot';
    END IF;

    DELETE FROM public.squad_assignments
    WHERE discord_id = p_discord_id AND position_slot = p_slot;
    INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
    VALUES (p_discord_id, p_slot, p_reserve_card_id);

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- T011 peer guards — progression/recovery RPCs block listed cards
-- ---------------------------------------------------------------------------

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
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);

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
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'drill');

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

CREATE OR REPLACE FUNCTION public.start_player_evolution(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_track_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_active INTEGER;
    v_cooldown_hours INTEGER;
    v_energy_cost INTEGER;
    v_card RECORD;
    v_goal INTEGER;
    v_evo_id UUID;
    v_energy INTEGER;
    v_coins BIGINT;
    v_last_started TIMESTAMPTZ;
    v_active_count INTEGER;
    v_is_replacement BOOLEAN;
    v_cooldown_ends TIMESTAMPTZ;
    v_coin_cost BIGINT;
    v_ovr INTEGER;
    v_min_level INTEGER;
    v_econ JSONB;
    v_flat BIGINT;
    v_ovr_mult INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'start_evolution');
    PERFORM public.sync_action_energy(p_owner_id);

    v_max_active := public.get_game_config_int('evolution_max_active', 3)::INTEGER;
    v_cooldown_hours := public.get_game_config_int('evolution_cooldown_hours', 10)::INTEGER;

    v_energy_cost := public.get_game_config_int('evolution_start_energy', 25)::INTEGER;
    v_flat := public.get_game_config_int('evolution_start_flat', 500);
    v_ovr_mult := public.get_game_config_int('evolution_start_ovr_mult', 5)::INTEGER;

    IF p_track_id NOT IN ('pace_boost', 'shooting_star', 'def_wall') THEN
        RAISE EXCEPTION 'Unknown evolution track';
    END IF;

    v_min_level := CASE p_track_id
        WHEN 'pace_boost' THEN 5
        WHEN 'shooting_star' THEN 10
        WHEN 'def_wall' THEN 8
        ELSE 1
    END;

    v_goal := 3;

    SELECT action_energy, coins, last_evolution_started_at
    INTO v_energy, v_coins, v_last_started
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    SELECT COUNT(*)::INTEGER INTO v_active_count
    FROM public.active_evolutions
    WHERE owner_id = p_owner_id AND status = 'active';

    IF v_active_count >= v_max_active THEN
        RAISE EXCEPTION 'You already have % evolutions in progress. Wait for one to complete or cancel an existing one.', v_max_active;
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE owner_id = p_owner_id
          AND status = 'cancelled'
          AND cancelled_at > COALESCE(v_last_started, '-infinity'::timestamptz)
    ) INTO v_is_replacement;

    IF NOT v_is_replacement AND v_last_started IS NOT NULL THEN
        v_cooldown_ends := v_last_started + (v_cooldown_hours || ' hours')::interval;
        IF NOW() < v_cooldown_ends THEN
            RAISE EXCEPTION 'Next evolution available in %',
                to_char(v_cooldown_ends - NOW(), 'FMHH24"h "FMMI"m"');
        END IF;
    END IF;

    SELECT id, owner_id, overall, level INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF v_card.id IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;

    IF v_card.level < v_min_level THEN
        RAISE EXCEPTION 'Player level too low for this evolution (requires level %)', v_min_level;
    END IF;

    v_ovr := v_card.overall;
    v_coin_cost := (v_flat + v_ovr_mult * v_ovr)::BIGINT;

    IF v_energy < v_energy_cost THEN
        RAISE EXCEPTION 'Insufficient action energy (% required)', v_energy_cost;
    END IF;
    IF v_coins < v_coin_cost THEN
        RAISE EXCEPTION 'Insufficient coins (% coins required)', v_coin_cost;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'This player is already evolving – complete or cancel the current track first';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND evolution_id = p_track_id AND status = 'completed'
    ) THEN
        RAISE EXCEPTION 'This player has already completed that evolution track';
    END IF;

    INSERT INTO public.active_evolutions (
        card_id, owner_id, evolution_id, target_metric,
        current_progress, target_goal, matches_played, matches_required,
        status, rewards_applied, started_at
    ) VALUES (
        p_card_id, p_owner_id, p_track_id, 'matches',
        0, v_goal, 0, v_goal,
        'active', FALSE, NOW()
    )
    RETURNING id INTO v_evo_id;

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_coin_cost,
        -v_energy_cost,
        'evolution_start',
        NULL,
        jsonb_build_object('card_id', p_card_id, 'track_id', p_track_id, 'evo_id', v_evo_id)
    );

    UPDATE public.players
    SET last_evolution_started_at = NOW()
    WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object(
        'evo_id', v_evo_id,
        'coin_cost', v_coin_cost,
        'energy_cost', v_energy_cost,
        'economy', v_econ
    );
END;
$$;

-- Soft / remaining gap wires

CREATE OR REPLACE FUNCTION public.create_transfer_listing(
    p_seller_id BIGINT,
    p_card_id UUID,
    p_price BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_slot_cap INTEGER;
    v_active_count INTEGER;
    v_ttl_hours INTEGER;
    v_cooldown_hours INTEGER;
    v_floor_mult NUMERIC;
    v_ceil_mult NUMERIC;
    v_fair_value BIGINT;
    v_price_floor BIGINT;
    v_price_ceil BIGINT;
    v_tax_bps BIGINT;
    v_listing_id UUID;
    v_expires_at TIMESTAMPTZ;
BEGIN
    IF NOT public.p2p_transfer_market_enabled() THEN
        RAISE EXCEPTION 'Transfer market is disabled';
    END IF;

    PERFORM public.assert_not_in_match(p_seller_id);

    -- Serialize per-club slot checks across concurrent listing attempts.
    PERFORM 1
    FROM public.players
    WHERE discord_id = p_seller_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Seller not found';
    END IF;

    SELECT *
    INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id
      AND owner_id = p_seller_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;
    PERFORM public.assert_card_action_allowed(p_seller_id, p_card_id, 'list_transfer');
    IF COALESCE(v_card.is_retired, FALSE) THEN
        RAISE EXCEPTION 'Cannot list a retired player';
    END IF;
    IF COALESCE(v_card.in_academy, FALSE) THEN
        RAISE EXCEPTION 'Cannot list a player in the academy';
    END IF;
    IF v_card.injury_tier IS NOT NULL OR COALESCE(v_card.in_hospital, FALSE) THEN
        RAISE EXCEPTION 'Cannot list an injured player';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    ) THEN
        RAISE EXCEPTION 'Cannot list a player in your starting 11';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot list a player in active training';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot list a player in an active evolution';
    END IF;

    PERFORM public.assert_card_not_on_transfer_list(p_card_id);

    v_slot_cap := public.get_game_config_int('transfer_listing_slot_cap', 5)::INTEGER;
    SELECT COUNT(*)::INTEGER
    INTO v_active_count
    FROM public.transfer_listings
    WHERE seller_id = p_seller_id AND status = 'active';
    IF v_active_count >= v_slot_cap THEN
        RAISE EXCEPTION 'Listing slots full (max % active listings)', v_slot_cap;
    END IF;

    v_cooldown_hours :=
        public.get_game_config_int('transfer_relist_cooldown_hours', 6)::INTEGER;
    IF EXISTS (
        SELECT 1
        FROM public.transfer_sales_log
        WHERE buyer_id = p_seller_id
          AND card_id = p_card_id
          AND created_at > NOW() - make_interval(hours => v_cooldown_hours)
    ) THEN
        RAISE EXCEPTION
            'Card recently acquired via transfer; wait % hours before relisting',
            v_cooldown_hours;
    END IF;

    v_floor_mult := COALESCE(
        (public.get_game_config('transfer_price_floor_mult') #>> '{}')::NUMERIC,
        0.75
    );
    v_ceil_mult := COALESCE(
        (public.get_game_config('transfer_price_ceil_mult') #>> '{}')::NUMERIC,
        2.5
    );
    v_fair_value := public.compute_agent_offer(
        v_card.overall,
        v_card.rarity,
        public.card_age_from_dob(v_card.date_of_birth),
        v_card.potential
    );
    v_price_floor := GREATEST(50, floor(v_fair_value * v_floor_mult)::BIGINT);
    v_price_ceil := GREATEST(
        v_price_floor,
        floor(v_fair_value * v_ceil_mult)::BIGINT
    );
    IF p_price IS NULL OR p_price < v_price_floor OR p_price > v_price_ceil THEN
        RAISE EXCEPTION 'Price must be between % and %', v_price_floor, v_price_ceil;
    END IF;

    v_ttl_hours := public.get_game_config_int('transfer_listing_ttl_hours', 72)::INTEGER;
    v_expires_at := NOW() + make_interval(hours => v_ttl_hours);
    INSERT INTO public.transfer_listings (
        seller_id, card_id, price_coins, status, expires_at
    ) VALUES (
        p_seller_id, p_card_id, p_price, 'active', v_expires_at
    ) RETURNING id INTO v_listing_id;

    v_tax_bps := public.get_game_config_int('transfer_tax_bps', 1000);
    RETURN jsonb_build_object(
        'listing_id', v_listing_id,
        'card_id', p_card_id,
        'price_coins', p_price,
        'seller_net_if_sold', p_price - floor(p_price * v_tax_bps / 10000.0)::BIGINT,
        'expires_at', v_expires_at,
        'active_listings', v_active_count + 1,
        'slot_cap', v_slot_cap
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.cancel_transfer_listing(
    p_seller_id BIGINT,
    p_listing_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_listing public.transfer_listings%ROWTYPE;
BEGIN
    SELECT *
    INTO v_listing
    FROM public.transfer_listings
    WHERE id = p_listing_id
      AND seller_id = p_seller_id
      AND status = 'active'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active listing not found or not owned';
    END IF;

    PERFORM public.assert_card_action_allowed(p_seller_id, v_listing.card_id, 'cancel_listing');

    UPDATE public.transfer_listings
    SET status = 'cancelled',
        cancelled_at = NOW()
    WHERE id = p_listing_id;

    RETURN jsonb_build_object(
        'listing_id', p_listing_id,
        'card_id', v_listing.card_id,
        'status', 'cancelled'
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ovr INTEGER;
    v_rarity TEXT;
    v_potential INTEGER;
    v_dob DATE;
    v_age INTEGER;
    v_retired BOOLEAN;
    v_injury_tier INTEGER;
    v_in_hospital BOOLEAN;
    v_sale_value BIGINT;
    v_sale_count INTEGER;
    v_cap INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.assert_card_action_allowed(p_club_id, p_card_id, 'agent_sell');

    v_cap := public.get_game_config_int('agent_sale_daily_cap', 10)::INTEGER;

    INSERT INTO public.agent_sale_daily_log (club_id, sale_date, count)
    VALUES (p_club_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, sale_date)
    DO UPDATE SET count = agent_sale_daily_log.count + 1
    RETURNING count INTO v_sale_count;

    IF v_sale_count > v_cap THEN
        RAISE EXCEPTION 'Daily agent sale limit reached (max % per day)', v_cap;
    END IF;

    SELECT
        overall, rarity, potential, date_of_birth, COALESCE(is_retired, FALSE),
        injury_tier, COALESCE(in_hospital, FALSE)
    INTO
        v_ovr, v_rarity, v_potential, v_dob, v_retired,
        v_injury_tier, v_in_hospital
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_club_id
    FOR UPDATE;

    IF v_ovr IS NULL THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;
    IF v_retired THEN
        RAISE EXCEPTION 'Cannot sell a retired player';
    END IF;
    IF v_injury_tier IS NOT NULL OR v_in_hospital THEN
        RAISE EXCEPTION 'Cannot sell an injured player';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_card_id
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in your starting 11';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in active training';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in an active evolution';
    END IF;

    v_age := public.card_age_from_dob(v_dob);
    v_sale_value := public.compute_agent_offer(v_ovr, v_rarity, v_age, v_potential);

    DELETE FROM public.player_cards WHERE id = p_card_id;

    PERFORM public.apply_club_economy(
        p_club_id, v_sale_value, 0, 'agent_sale',
        'agent_sale:' || p_card_id::TEXT,
        jsonb_build_object(
            'card_id', p_card_id, 'ovr', v_ovr, 'rarity', v_rarity,
            'age', v_age, 'potential', v_potential
        )
    );

    RETURN v_sale_value;
END;
$$;

CREATE OR REPLACE FUNCTION public.train_with_fodder(
    p_owner_id BIGINT,
    p_target_id UUID,
    p_fodder_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_target_owner BIGINT;
    v_fodder_owner BIGINT;
    v_fodder_level INTEGER;
    v_fodder_overall INTEGER;
    v_target_overall INTEGER;
    v_target_potential INTEGER;
    v_fusion_xp INTEGER;
    v_fusion_count INTEGER;
    v_fusion_limit CONSTANT INTEGER := 3;
    v_fusion_cost BIGINT;
    v_coins BIGINT;
    v_xp_result JSONB;
    v_econ JSONB;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.assert_card_not_on_transfer_list(p_target_id);
    PERFORM public.assert_card_not_on_transfer_list(p_fodder_id);
    PERFORM public.assert_card_action_allowed(p_owner_id, p_target_id, 'fusion');
    PERFORM public.assert_card_action_allowed(p_owner_id, p_fodder_id, 'fusion');
    PERFORM public.sync_action_energy(p_owner_id);

    v_fusion_cost := public.get_game_config_int('fusion_coins', 200);

    SELECT coins INTO v_coins
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF v_coins < v_fusion_cost THEN
        RAISE EXCEPTION 'Insufficient coins (% coins required for fusion)', v_fusion_cost;
    END IF;

    SELECT owner_id, overall, potential
    INTO v_target_owner, v_target_overall, v_target_potential
    FROM public.player_cards
    WHERE id = p_target_id
    FOR UPDATE;

    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN
        RAISE EXCEPTION 'Target player card not found or not owned by you';
    END IF;

    SELECT owner_id, level, overall
    INTO v_fodder_owner, v_fodder_level, v_fodder_overall
    FROM public.player_cards
    WHERE id = p_fodder_id
    FOR UPDATE;

    IF v_fodder_owner IS NULL OR v_fodder_owner != p_owner_id THEN
        RAISE EXCEPTION 'Fodder player card not found or not owned by you';
    END IF;

    IF p_target_id = p_fodder_id THEN
        RAISE EXCEPTION 'Cannot use the same card as both target and fodder';
    END IF;

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_fodder_id) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in your starting 11';
    END IF;

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_target_id) THEN
        RAISE EXCEPTION 'Cannot upgrade a player card that is currently in your starting 11';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_fodder_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in active training';
    END IF;

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_fodder_id AND status = 'active') THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in an active evolution';
    END IF;

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_target_id AND status = 'active') THEN
        RAISE EXCEPTION 'Cannot upgrade a player card that is currently in an active evolution';
    END IF;

    INSERT INTO public.fusion_daily_log (club_id, fusion_date, count)
    VALUES (p_owner_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, fusion_date)
    DO UPDATE SET count = fusion_daily_log.count + 1
    RETURNING count INTO v_fusion_count;

    IF v_fusion_count > v_fusion_limit THEN
        RAISE EXCEPTION 'Daily fusion limit reached (max % per day)', v_fusion_limit;
    END IF;

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_fusion_cost,
        0,
        'fusion',
        NULL,
        jsonb_build_object('target_id', p_target_id, 'fodder_id', p_fodder_id)
    );

    v_fusion_xp := 50
        + (GREATEST(1, v_fodder_level) * 8)
        + (GREATEST(0, v_fodder_overall) * 2);

    DELETE FROM public.player_cards WHERE id = p_fodder_id;

    v_xp_result := public.apply_card_xp(p_target_id, v_fusion_xp, 'fusion');

    RETURN jsonb_build_object(
        'fusion_xp', v_fusion_xp,
        'fusion_cost', v_fusion_cost,
        'levels_gained', COALESCE((v_xp_result->>'levels_gained')::INTEGER, 0),
        'skill_points_granted', COALESCE((v_xp_result->>'skill_points_granted')::INTEGER, 0),
        'new_level', COALESCE((v_xp_result->>'new_level')::INTEGER, 1),
        'new_ovr', v_target_overall,
        'xp_wasted', COALESCE((v_xp_result->>'xp_wasted')::INTEGER, 0),
        'economy', v_econ
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.allocate_skill_point(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_stat TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_col TEXT;
    v_points INTEGER;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_overall INTEGER;
    v_potential INTEGER;
    v_alloc_count INTEGER;
    v_alloc_reset DATE;
    v_alloc_cap CONSTANT INTEGER := 15;
    v_pacing_until CONSTANT DATE := DATE '2026-08-06';
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'allocate');

    v_col := CASE lower(p_stat)
        WHEN 'pac' THEN 'pac'
        WHEN 'sho' THEN 'sho'
        WHEN 'pas' THEN 'pas'
        WHEN 'dri' THEN 'dri'
        WHEN 'def' THEN 'def'
        WHEN 'phy' THEN 'phy'
        ELSE NULL
    END;
    IF v_col IS NULL THEN
        RAISE EXCEPTION 'Invalid stat';
    END IF;

    EXECUTE format(
        'SELECT skill_points, overall, potential, %I, daily_alloc_count, alloc_reset_date '
        || 'FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',
        v_col
    ) INTO v_points, v_overall, v_potential, v_current, v_alloc_count, v_alloc_reset
    USING p_card_id, p_owner_id;

    IF v_points IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;
    IF v_points <= 0 THEN
        RAISE EXCEPTION 'No skill points available';
    END IF;
    IF v_current >= 99 THEN
        RAISE EXCEPTION 'Stat already at maximum';
    END IF;
    IF v_overall >= v_potential THEN
        RAISE EXCEPTION 'Player is already at maximum overall for their potential';
    END IF;

    IF CURRENT_DATE <= v_pacing_until THEN
        IF v_alloc_reset IS NULL OR v_alloc_reset < CURRENT_DATE THEN
            v_alloc_count := 0;
            UPDATE public.player_cards
            SET daily_alloc_count = 0, alloc_reset_date = CURRENT_DATE
            WHERE id = p_card_id;
        END IF;
        IF v_alloc_count >= v_alloc_cap THEN
            RAISE EXCEPTION 'Daily skill allocation limit reached for this player (max % per day during pacing period)', v_alloc_cap;
        END IF;
    END IF;

    v_new_val := v_current + 1;

    EXECUTE format(
        'UPDATE public.player_cards SET %I = $1, skill_points = skill_points - 1, '
        || 'skill_points_spent = skill_points_spent + 1, daily_alloc_count = daily_alloc_count + 1, '
        || 'alloc_reset_date = CURRENT_DATE WHERE id = $2',
        v_col
    ) USING v_new_val, p_card_id;

    v_new_ovr := public.recalculate_card_ovr(p_card_id);

    IF v_new_ovr > v_potential THEN
        RAISE EXCEPTION 'Would exceed maximum overall for their potential';
    END IF;

    RETURN jsonb_build_object('new_ovr', v_new_ovr, 'stat', upper(v_col), 'new_value', v_new_val);
END;
$$;

CREATE OR REPLACE FUNCTION public.process_recovery_batch(
    p_owner_id BIGINT,
    p_card_ids UUID[]
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_energy INTEGER;
    v_n INTEGER;
    v_cost_each INTEGER;
    v_grant INTEGER;
    v_total INTEGER;
    v_econ JSONB;
    v_players JSONB := '[]'::JSONB;
    v_card_id UUID;
    v_fatigue INTEGER;
    v_old_fatigue INTEGER;
    v_injury INTEGER;
    v_in_hospital BOOLEAN;
    v_in_academy BOOLEAN;
    v_gained INTEGER;
    v_seen UUID[] := ARRAY[]::UUID[];
BEGIN
    IF p_card_ids IS NULL THEN
        RAISE EXCEPTION 'Select between 1 and 3 players';
    END IF;

    v_n := cardinality(p_card_ids);
    IF v_n < 1 OR v_n > 3 THEN
        RAISE EXCEPTION 'Select between 1 and 3 players';
    END IF;

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        IF v_card_id = ANY (v_seen) THEN
            RAISE EXCEPTION 'Duplicate players in recovery selection';
        END IF;
        v_seen := array_append(v_seen, v_card_id);
    END LOOP;

    PERFORM public.sync_action_energy(p_owner_id);

    SELECT action_energy
    INTO v_energy
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    PERFORM public.assert_not_in_match(p_owner_id);

    v_cost_each := public.get_game_config_int('fatigue_recovery_energy', 5)::INTEGER;
    v_grant := public.get_game_config_int('fatigue_recovery_session', 40)::INTEGER;
    v_total := v_n * v_cost_each;

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        PERFORM public.assert_card_not_on_transfer_list(v_card_id);
        PERFORM public.assert_card_action_allowed(p_owner_id, v_card_id, 'recover_fatigue');

        SELECT fatigue, injury_tier, COALESCE(in_hospital, FALSE), COALESCE(in_academy, FALSE)
        INTO v_fatigue, v_injury, v_in_hospital, v_in_academy
        FROM public.player_cards
        WHERE id = v_card_id
          AND owner_id = p_owner_id
          AND COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Player card not found or not owned';
        END IF;

        IF v_in_academy THEN
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
            WHERE card_id = v_card_id AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'Player is in an active evolution track';
        END IF;
    END LOOP;

    IF v_energy < v_total THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    v_econ := public.apply_club_economy(
        p_owner_id,
        0,
        -v_total,
        'recovery_batch',
        NULL,
        jsonb_build_object(
            'card_ids', to_jsonb(p_card_ids),
            'recovery_amount', v_grant,
            'player_count', v_n
        )
    );

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        SELECT fatigue INTO v_fatigue
        FROM public.player_cards
        WHERE id = v_card_id
        FOR UPDATE;

        v_old_fatigue := v_fatigue;
        v_fatigue := LEAST(100, v_fatigue + v_grant);
        v_gained := v_fatigue - v_old_fatigue;

        UPDATE public.player_cards
        SET fatigue = v_fatigue
        WHERE id = v_card_id;

        v_players := v_players || jsonb_build_array(
            jsonb_build_object(
                'card_id', v_card_id,
                'fatigue_gained', v_gained,
                'new_fatigue', v_fatigue
            )
        );
    END LOOP;

    RETURN jsonb_build_object(
        'energy_spent', v_total,
        'coins_spent', 0,
        'xp_gained', 0,
        'recovery_amount', v_grant,
        'players', v_players,
        'economy', v_econ
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
    PERFORM public.assert_card_action_allowed(p_owner_id, p_player_card_id, 'discharge_hospital');

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

CREATE OR REPLACE FUNCTION public.claim_evolution_reward(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card_id UUID;
    v_evo_id TEXT;
    v_progress INTEGER;
    v_goal INTEGER;
    v_stat_col TEXT;
    v_reward_max INTEGER := 5;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_applied INTEGER;
    v_status TEXT;
    v_overall INTEGER;
    v_potential INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.card_id, e.evolution_id,
           COALESCE(e.matches_played, e.current_progress),
           COALESCE(e.matches_required, e.target_goal),
           e.status
    INTO v_card_id, v_evo_id, v_progress, v_goal, v_status
    FROM public.active_evolutions e
    JOIN public.player_cards c ON c.id = e.card_id
    WHERE e.id = p_evo_id AND c.owner_id = p_owner_id
    FOR UPDATE;

    IF v_card_id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
    END IF;
    PERFORM public.assert_card_action_allowed(p_owner_id, v_card_id, 'claim_evolution');
    IF v_status <> 'active' THEN
        RAISE EXCEPTION 'Evolution is not active';
    END IF;
    IF v_progress < v_goal THEN
        RAISE EXCEPTION 'Evolution not complete';
    END IF;

    SELECT overall, potential
    INTO v_overall, v_potential
    FROM public.player_cards
    WHERE id = v_card_id
    FOR UPDATE;

    v_stat_col := CASE v_evo_id
        WHEN 'pace_boost' THEN 'pac'
        WHEN 'shooting_star' THEN 'sho'
        WHEN 'def_wall' THEN 'def'
        ELSE 'pac'
    END;

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1',
        v_stat_col
    ) INTO v_current USING v_card_id;

    v_applied := public.evolution_stat_reward_steps(v_card_id, v_stat_col, v_reward_max);
    v_new_val := v_current;
    IF v_applied > 0 THEN
        v_new_val := v_current + v_applied;
        EXECUTE format(
            'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
            v_stat_col
        ) USING v_new_val, v_card_id;
    END IF;

    v_new_ovr := public.recalculate_card_ovr(v_card_id);

    UPDATE public.active_evolutions
    SET
        status = 'completed',
        rewards_applied = TRUE,
        completed_at = NOW()
    WHERE id = p_evo_id;

    RETURN jsonb_build_object(
        'new_ovr', v_new_ovr,
        'stat', upper(v_stat_col),
        'reward', v_applied,
        'reward_max', v_reward_max,
        'reward_clamped', (v_applied > 0 AND v_applied < v_reward_max),
        'blocked_by_cap', (v_applied = 0 AND v_overall >= v_potential AND v_current < 99)
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.cancel_player_evolution(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_evo RECORD;
    v_fee CONSTANT INTEGER := 100;
    v_econ JSONB;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.id, e.card_id, e.owner_id, e.status
    INTO v_evo
    FROM public.active_evolutions e
    WHERE e.id = p_evo_id AND e.owner_id = p_owner_id
    FOR UPDATE;

    IF v_evo.id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
    END IF;
    IF v_evo.status <> 'active' THEN
        RAISE EXCEPTION 'Only active evolutions can be cancelled';
    END IF;

    PERFORM public.assert_card_action_allowed(p_owner_id, v_evo.card_id, 'cancel_evolution');

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_fee,
        0,
        'evolution_cancel',
        'evolution_cancel:' || p_evo_id::TEXT,
        jsonb_build_object('evo_id', p_evo_id)
    );

    IF COALESCE((v_econ->>'replay')::BOOLEAN, FALSE) THEN
        RETURN jsonb_build_object('cancelled', TRUE, 'fee', v_fee, 'replay', TRUE);
    END IF;

    UPDATE public.active_evolutions
    SET
        status = 'cancelled',
        cancelled_at = NOW(),
        matches_played = 0,
        current_progress = 0
    WHERE id = p_evo_id;

    RETURN jsonb_build_object('cancelled', TRUE, 'fee', v_fee);
END;
$$;

CREATE OR REPLACE FUNCTION public.promote_academy_player(
    p_owner_id BIGINT,
    p_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_senior INTEGER;
    v_cap INTEGER;
    v_ready INTEGER;
    v_ovr INTEGER;
BEGIN
    SELECT * INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Card not found';
    END IF;
    IF COALESCE(v_card.is_retired, FALSE) THEN
        RAISE EXCEPTION 'Card is retired';
    END IF;
    IF NOT COALESCE(v_card.in_academy, FALSE) THEN
        RAISE EXCEPTION 'Not an academy player';
    END IF;

    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'academy_promote');

    v_cap := public.get_game_config_int('senior_roster_cap', 48)::INTEGER;
    SELECT COUNT(*)::INTEGER INTO v_senior
    FROM public.player_cards
    WHERE owner_id = p_owner_id
      AND in_academy = FALSE
      AND COALESCE(is_retired, FALSE) = FALSE;

    IF v_senior >= v_cap THEN
        RAISE EXCEPTION 'Senior roster is full (%/%). Sell or release a senior player first.', v_senior, v_cap;
    END IF;

    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;

    UPDATE public.player_cards
    SET in_academy = FALSE,
        academy_progress = 0,
        academy_seated_at = NULL
    WHERE id = p_card_id;

    v_ready := public.get_game_config_int('academy_ready_ovr', 65)::INTEGER;
    v_ovr := v_card.overall;

    RETURN jsonb_build_object(
        'card_id', p_card_id,
        'overall', v_ovr,
        'potential', v_card.potential,
        'early_promote', v_ovr < v_ready
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.release_academy_player(
    p_owner_id BIGINT,
    p_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_name TEXT;
BEGIN
    SELECT name INTO v_name
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id AND in_academy = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Not an academy player';
    END IF;

    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'academy_release');

    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;
    DELETE FROM public.player_cards WHERE id = p_card_id;

    RETURN jsonb_build_object(
        'released_card_id', p_card_id,
        'name', v_name
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.retire_player_card(p_card_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
    v_slot INTEGER;
    v_formation TEXT;
    v_role TEXT;
    v_promoted UUID;
    v_xi_count INTEGER;
    v_invalid BOOLEAN;
BEGIN
    SELECT owner_id INTO v_owner
    FROM public.player_cards
    WHERE id = p_card_id AND COALESCE(is_retired, FALSE) = FALSE
    FOR UPDATE;

    IF v_owner IS NULL THEN
        RAISE EXCEPTION 'Card not found or already retired';
    END IF;

    PERFORM public.assert_card_action_allowed(v_owner, p_card_id, 'retire');

    SELECT position_slot INTO v_slot
    FROM public.squad_assignments
    WHERE player_card_id = p_card_id;

    DELETE FROM public.squad_assignments
    WHERE player_card_id = p_card_id;

    UPDATE public.player_cards
    SET is_retired = TRUE,
        retired_at = NOW()
    WHERE id = p_card_id;

    v_promoted := NULL;

    IF v_slot IS NOT NULL THEN
        SELECT formation INTO v_formation
        FROM public.squads
        WHERE discord_id = v_owner;

        v_role := public.formation_slot_role(COALESCE(v_formation, '4-4-2'), v_slot);

        SELECT pc.id INTO v_promoted
        FROM public.player_cards pc
        WHERE pc.owner_id = v_owner
          AND COALESCE(pc.is_retired, FALSE) = FALSE
          AND pc.position = v_role
          AND NOT EXISTS (
              SELECT 1 FROM public.squad_assignments sa
              WHERE sa.player_card_id = pc.id
          )
        ORDER BY pc.overall DESC, pc.id ASC
        LIMIT 1;

        IF v_promoted IS NOT NULL THEN
            INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
            VALUES (v_owner, v_slot, v_promoted);
        ELSE
            UPDATE public.players
            SET squad_invalid = TRUE
            WHERE discord_id = v_owner;
        END IF;
    END IF;

    SELECT COUNT(*) INTO v_xi_count
    FROM public.squad_assignments
    WHERE discord_id = v_owner;

    IF v_xi_count = 11 THEN
        UPDATE public.players
        SET squad_invalid = FALSE
        WHERE discord_id = v_owner;
    END IF;

    SELECT COALESCE(squad_invalid, FALSE) INTO v_invalid
    FROM public.players
    WHERE discord_id = v_owner;

    RETURN jsonb_build_object(
        'card_id', p_card_id,
        'owner_id', v_owner,
        'retired_at', NOW(),
        'vacated_slot', v_slot,
        'promoted_card_id', v_promoted,
        'squad_invalid', COALESCE(v_invalid, FALSE)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    missing TEXT := '';
BEGIN
    IF to_regprocedure('public.assert_card_action_allowed(bigint,uuid,text)') IS NULL THEN
        missing := missing || 'assert_card_action_allowed ';
    END IF;
    IF to_regprocedure('public.card_primary_state(uuid)') IS NULL THEN
        missing := missing || 'card_primary_state ';
    END IF;
    IF missing <> '' THEN
        RAISE EXCEPTION '075 schema guard failed: %', missing;
    END IF;
END;
$$;


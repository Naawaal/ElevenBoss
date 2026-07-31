CREATE OR REPLACE FUNCTION public.train_with_fodder(p_owner_id bigint, p_target_id uuid, p_fodder_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
$function$

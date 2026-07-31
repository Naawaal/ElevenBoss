CREATE OR REPLACE FUNCTION public.transfer_mentor_xp(p_owner_id bigint, p_source_card_id uuid, p_target_card_id uuid, p_mentor_units integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    v_sp_per_unit CONSTANT INTEGER := 5;
    v_xp_per_unit CONSTANT INTEGER := 500;
    v_daily_limit CONSTANT INTEGER := 3;
    v_l_max CONSTANT INTEGER := 100;
    v_units INTEGER;
    v_sp_spent INTEGER;
    v_xp_granted INTEGER;
    v_src public.player_cards%ROWTYPE;
    v_tgt public.player_cards%ROWTYPE;
    v_first UUID;
    v_second UUID;
    v_today DATE;
    v_used INTEGER;
    v_headroom INTEGER;
    v_cap_xp INTEGER;
    v_xp_result JSONB;
    v_wasted INTEGER;
BEGIN
    v_units := COALESCE(p_mentor_units, 0);
    IF v_units < 1 THEN
        RAISE EXCEPTION 'Invalid mentor unit amount';
    END IF;

    IF p_source_card_id IS NULL OR p_target_card_id IS NULL THEN
        RAISE EXCEPTION 'Source and target cards are required';
    END IF;

    IF p_source_card_id = p_target_card_id THEN
        RAISE EXCEPTION 'Source and target must differ';
    END IF;

    PERFORM public.assert_card_not_on_transfer_list(p_source_card_id);
    PERFORM public.assert_card_not_on_transfer_list(p_target_card_id);

    v_sp_spent := v_units * v_sp_per_unit;
    v_xp_granted := v_units * v_xp_per_unit;
    v_today := (timezone('utc', now()))::date;

    -- Deterministic lock order by id
    IF p_source_card_id::text < p_target_card_id::text THEN
        v_first := p_source_card_id;
        v_second := p_target_card_id;
    ELSE
        v_first := p_target_card_id;
        v_second := p_source_card_id;
    END IF;

    PERFORM 1 FROM public.player_cards WHERE id = v_first FOR UPDATE;
    PERFORM 1 FROM public.player_cards WHERE id = v_second FOR UPDATE;

    SELECT * INTO v_src FROM public.player_cards WHERE id = p_source_card_id;
    IF NOT FOUND OR v_src.owner_id IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Source card not found or not owned';
    END IF;

    SELECT * INTO v_tgt FROM public.player_cards WHERE id = p_target_card_id;
    IF NOT FOUND OR v_tgt.owner_id IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Target card not found or not owned';
    END IF;

    IF COALESCE(v_src.overall, 0) < COALESCE(v_src.potential, 0) THEN
        RAISE EXCEPTION 'Source card has not reached potential ceiling';
    END IF;

    IF COALESCE(v_src.skill_points, 0) < v_sp_spent THEN
        RAISE EXCEPTION 'Insufficient skill points';
    END IF;

    IF COALESCE(v_tgt.overall, 0) >= COALESCE(v_tgt.potential, 0) THEN
        RAISE EXCEPTION 'Target card is already maxed';
    END IF;

    IF COALESCE(v_tgt.level, 1) >= v_l_max THEN
        RAISE EXCEPTION 'Target cannot receive more XP';
    END IF;

    v_cap_xp := public.cumulative_xp_for_level(v_l_max);
    v_headroom := GREATEST(0, v_cap_xp - COALESCE(v_tgt.xp, 0));
    IF v_headroom < v_xp_granted THEN
        RAISE EXCEPTION 'Target cannot absorb mentor XP';
    END IF;

    -- Does not touch daily_alloc_count / alloc_reset_date (mentor ≠ allocate)
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.mentor_transfer_log
    WHERE club_id = p_owner_id
      AND transfer_date = v_today;

    IF v_used >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily mentor transfer limit (3) reached';
    END IF;

    UPDATE public.player_cards
    SET
        skill_points = skill_points - v_sp_spent,
        skill_points_spent = skill_points_spent + v_sp_spent
    WHERE id = p_source_card_id
      AND skill_points >= v_sp_spent;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Insufficient skill points';
    END IF;

    v_xp_result := public.apply_card_xp(p_target_card_id, v_xp_granted, 'mentor_transfer');
    v_wasted := COALESCE((v_xp_result->>'xp_wasted')::INTEGER, 0);
    IF v_wasted > 0 THEN
        RAISE EXCEPTION 'Target cannot absorb mentor XP';
    END IF;

    INSERT INTO public.mentor_transfer_log (
        club_id, source_card_id, target_card_id, mentor_units, sp_spent, xp_granted, transfer_date
    ) VALUES (
        p_owner_id, p_source_card_id, p_target_card_id, v_units, v_sp_spent, v_xp_granted, v_today
    );

    v_used := v_used + 1;

    SELECT skill_points INTO v_src.skill_points
    FROM public.player_cards WHERE id = p_source_card_id;

    RETURN jsonb_build_object(
        'source_card_id', p_source_card_id,
        'target_card_id', p_target_card_id,
        'mentor_units', v_units,
        'sp_spent', v_sp_spent,
        'xp_granted', v_xp_granted,
        'source_skill_points', COALESCE(v_src.skill_points, 0),
        'xp_result', v_xp_result,
        'transfers_used_today', v_used,
        'transfers_remaining_today', GREATEST(0, v_daily_limit - v_used)
    );
END;
$function$

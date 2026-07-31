CREATE OR REPLACE FUNCTION public.allocate_skill_point(p_owner_id bigint, p_card_id uuid, p_stat text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
$function$

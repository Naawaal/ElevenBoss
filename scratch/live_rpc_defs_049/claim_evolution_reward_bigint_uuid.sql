CREATE OR REPLACE FUNCTION public.claim_evolution_reward(p_owner_id bigint, p_evo_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
$function$

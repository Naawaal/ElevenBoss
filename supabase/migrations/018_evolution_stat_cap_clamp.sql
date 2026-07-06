-- Clamp evolution stat rewards to the 99 cap instead of hard-failing legacy claims.
CREATE OR REPLACE FUNCTION public.claim_evolution_reward(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_card_id UUID;
    v_evo_id TEXT;
    v_progress INTEGER;
    v_goal INTEGER;
    v_stat_col TEXT;
    v_reward INTEGER;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_applied INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.card_id, e.evolution_id, e.current_progress, e.target_goal
    INTO v_card_id, v_evo_id, v_progress, v_goal
    FROM public.active_evolutions e
    JOIN public.player_cards c ON c.id = e.card_id
    WHERE e.id = p_evo_id AND c.owner_id = p_owner_id
    FOR UPDATE;

    IF v_card_id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
    END IF;
    IF v_progress < v_goal THEN
        RAISE EXCEPTION 'Evolution not complete';
    END IF;

    v_stat_col := CASE v_evo_id
        WHEN 'pace_boost' THEN 'pac'
        WHEN 'shooting_star' THEN 'sho'
        WHEN 'def_wall' THEN 'def'
        ELSE 'pac'
    END;
    v_reward := 5;

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1 FOR UPDATE',
        v_stat_col
    ) INTO v_current USING v_card_id;

    v_new_val := LEAST(99, v_current + v_reward);
    v_applied := v_new_val - v_current;

    IF v_applied > 0 THEN
        EXECUTE format(
            'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
            v_stat_col
        ) USING v_new_val, v_card_id;
    END IF;

    v_new_ovr := public.recalculate_card_ovr(v_card_id);
    DELETE FROM public.active_evolutions WHERE id = p_evo_id;

    RETURN jsonb_build_object(
        'new_ovr', v_new_ovr,
        'stat', upper(v_stat_col),
        'reward', v_applied,
        'new_value', v_new_val
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.evolution_stat_reward_steps(p_card_id uuid, p_stat_col text, p_max_steps integer DEFAULT 5)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_current INTEGER;
    v_overall INTEGER;
    v_potential INTEGER;
    v_steps INTEGER := 0;
    v_trial INTEGER;
    v_trial_ovr INTEGER;
BEGIN
    EXECUTE format(
        'SELECT %I, overall, potential FROM public.player_cards WHERE id = $1',
        p_stat_col
    ) INTO v_current, v_overall, v_potential USING p_card_id;

    IF v_current IS NULL THEN
        RETURN 0;
    END IF;
    IF v_overall >= v_potential OR v_current >= 99 THEN
        RETURN 0;
    END IF;

    FOR i IN 1..GREATEST(0, p_max_steps) LOOP
        EXIT WHEN v_current + v_steps >= 99;
        v_trial := v_current + v_steps + 1;
        v_trial_ovr := public.peek_card_ovr(p_card_id, p_stat_col, v_trial);
        IF v_trial_ovr > v_potential THEN
            EXIT;
        END IF;
        v_steps := v_steps + 1;
    END LOOP;

    RETURN v_steps;
END;
$function$

CREATE OR REPLACE FUNCTION public.process_match_result(p_result text, p_card_ids uuid[], p_xp_amount integer, p_card_ratings numeric[] DEFAULT NULL::numeric[], p_xp_amounts integer[] DEFAULT NULL::integer[], p_match_history_id uuid DEFAULT NULL::uuid)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_card_id UUID;
    v_morale_delta INTEGER;
    v_i INTEGER;
    v_rating NUMERIC;
    v_recent JSONB;
    v_age INTEGER;
    v_pot INTEGER;
    v_init_pot INTEGER;
    v_high INTEGER;
    v_boost INTEGER;
    v_new_pot INTEGER;
    v_xp INTEGER;
    v_dob DATE;
    v_xp_applied TIMESTAMPTZ;
BEGIN
    IF p_match_history_id IS NOT NULL THEN
        SELECT xp_applied_at INTO v_xp_applied
        FROM public.match_history
        WHERE id = p_match_history_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'match_history row not found';
        END IF;
        IF v_xp_applied IS NOT NULL THEN
            RETURN TRUE;
        END IF;
    END IF;

    IF p_result = 'win' THEN
        v_morale_delta := 5;
    ELSIF p_result = 'draw' THEN
        v_morale_delta := 1;
    ELSE
        v_morale_delta := -5;
    END IF;

    FOR v_i IN 1..COALESCE(array_length(p_card_ids, 1), 0) LOOP
        v_card_id := p_card_ids[v_i];

        IF p_card_ratings IS NOT NULL AND array_length(p_card_ratings, 1) >= v_i THEN
            v_rating := p_card_ratings[v_i];
        ELSE
            v_rating := NULL;
        END IF;

        SELECT date_of_birth, potential, base_potential, recent_match_ratings
        INTO v_dob, v_pot, v_init_pot, v_recent
        FROM public.player_cards
        WHERE id = v_card_id AND COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE;

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        v_age := public.card_age_from_dob(v_dob);

        IF v_rating IS NOT NULL THEN
            v_recent := COALESCE(v_recent, '[]'::jsonb) || to_jsonb(v_rating);
            IF jsonb_array_length(v_recent) > 5 THEN
                v_recent := (
                    SELECT COALESCE(jsonb_agg(val ORDER BY ord), '[]'::jsonb)
                    FROM (
                        SELECT value AS val, ord
                        FROM jsonb_array_elements(v_recent) WITH ORDINALITY AS t(value, ord)
                        ORDER BY ord DESC
                        LIMIT 5
                    ) sub
                );
            END IF;

            v_init_pot := COALESCE(v_init_pot, v_pot);
            v_boost := 0;

            IF v_age BETWEEN 16 AND 21 AND jsonb_array_length(v_recent) >= 3 THEN
                SELECT COUNT(*)::INTEGER INTO v_high
                FROM jsonb_array_elements(v_recent) elem
                WHERE (elem #>> '{}')::NUMERIC >= 8.0;

                IF v_high >= 3 AND random() < 0.20 THEN
                    v_boost := 2 + floor(random() * 4)::INTEGER;
                    v_new_pot := LEAST(99, LEAST(v_pot + v_boost, v_init_pot + 10));
                    IF v_new_pot > v_pot THEN
                        v_pot := v_new_pot;
                    END IF;
                END IF;
            END IF;

            UPDATE public.player_cards
            SET
                age = v_age,
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta)),
                recent_match_ratings = v_recent,
                potential = v_pot
            WHERE id = v_card_id;
        ELSE
            UPDATE public.player_cards
            SET
                age = v_age,
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta))
            WHERE id = v_card_id;
        END IF;

        v_xp := p_xp_amount;
        IF p_xp_amounts IS NOT NULL AND array_length(p_xp_amounts, 1) >= v_i THEN
            v_xp := p_xp_amounts[v_i];
        END IF;

        PERFORM public.apply_card_xp(v_card_id, v_xp, 'match_simulation');
    END LOOP;

    PERFORM public.tick_evolution_match_progress(p_card_ids);

    IF p_match_history_id IS NOT NULL THEN
        UPDATE public.match_history
        SET xp_applied_at = NOW()
        WHERE id = p_match_history_id;
    END IF;

    RETURN TRUE;
END;
$function$

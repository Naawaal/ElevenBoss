-- 026: Per-card match XP amounts (US-23 AC-23e)

DROP FUNCTION IF EXISTS public.process_match_result(text, uuid[], integer, numeric[]);

CREATE OR REPLACE FUNCTION public.process_match_result(
    p_result TEXT,
    p_card_ids UUID[],
    p_xp_amount INTEGER,
    p_card_ratings NUMERIC[] DEFAULT NULL,
    p_xp_amounts INTEGER[] DEFAULT NULL
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
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
BEGIN
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

        SELECT age, potential, initial_potential, recent_match_ratings
        INTO v_age, v_pot, v_init_pot, v_recent
        FROM public.player_cards
        WHERE id = v_card_id
        FOR UPDATE;

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
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta)),
                recent_match_ratings = v_recent,
                potential = v_pot
            WHERE id = v_card_id;
        ELSE
            UPDATE public.player_cards
            SET morale = LEAST(100, GREATEST(10, morale + v_morale_delta))
            WHERE id = v_card_id;
        END IF;

        v_xp := p_xp_amount;
        IF p_xp_amounts IS NOT NULL AND array_length(p_xp_amounts, 1) >= v_i THEN
            v_xp := p_xp_amounts[v_i];
        END IF;

        PERFORM public.apply_card_xp(v_card_id, v_xp, 'match_simulation');
    END LOOP;

    PERFORM public.tick_evolution_match_progress(p_card_ids);
    RETURN TRUE;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_match_result(text, uuid[], integer, numeric[], integer[]) TO anon, authenticated, service_role;

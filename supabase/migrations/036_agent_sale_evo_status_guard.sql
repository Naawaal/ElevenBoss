-- Fix process_agent_sale: only block active evolutions (not completed/cancelled history).

CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ovr INTEGER;
    v_rarity TEXT;
    v_sale_value BIGINT;
    v_sale_count INTEGER;
    v_cap INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);

    v_cap := public.get_game_config_int('agent_sale_daily_cap', 10)::INTEGER;

    INSERT INTO public.agent_sale_daily_log (club_id, sale_date, count)
    VALUES (p_club_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, sale_date)
    DO UPDATE SET count = agent_sale_daily_log.count + 1
    RETURNING count INTO v_sale_count;

    IF v_sale_count > v_cap THEN
        RAISE EXCEPTION 'Daily agent sale limit reached (max % per day)', v_cap;
    END IF;

    SELECT overall, rarity INTO v_ovr, v_rarity
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_club_id
    FOR UPDATE;

    IF v_ovr IS NULL THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_card_id) THEN
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

    v_sale_value := public.compute_agent_offer(v_ovr, v_rarity);

    DELETE FROM public.player_cards WHERE id = p_card_id;

    PERFORM public.apply_club_economy(
        p_club_id,
        v_sale_value,
        0,
        'agent_sale',
        'agent_sale:' || p_card_id::TEXT,
        jsonb_build_object('card_id', p_card_id, 'ovr', v_ovr, 'rarity', v_rarity)
    );

    RETURN v_sale_value;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale(BIGINT, UUID) TO anon, authenticated, service_role;

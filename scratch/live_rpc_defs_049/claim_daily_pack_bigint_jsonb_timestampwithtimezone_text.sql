CREATE OR REPLACE FUNCTION public.claim_daily_pack(p_club_id bigint, p_cards jsonb, p_topgg_vote_at timestamp with time zone, p_idempotency_key text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_last TIMESTAMPTZ;
    v_consumed TIMESTAMPTZ;
    v_now TIMESTAMPTZ := NOW();
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_remaining INTEGER;
    v_dob DATE;
    v_cooldown_hours INTEGER;
    v_prior JSONB;
    v_result JSONB;
BEGIN
    IF p_idempotency_key IS NOT NULL THEN
        SELECT result_json INTO v_prior
        FROM public.pack_claim_runs
        WHERE idempotency_key = p_idempotency_key;

        IF FOUND THEN
            RETURN jsonb_build_object(
                'status', 'already_applied',
                'reason', NULL,
                'data', v_prior
            );
        END IF;
    END IF;

    IF p_cards IS NULL OR jsonb_array_length(p_cards) < 1 THEN
        RETURN jsonb_build_object(
            'status', 'rejected',
            'reason', 'empty_pack',
            'data', '{}'::JSONB
        );
    END IF;

    IF p_topgg_vote_at IS NULL THEN
        RAISE EXCEPTION 'VOTE_REQUIRED';
    END IF;

    IF p_topgg_vote_at < v_now - INTERVAL '12 hours' THEN
        RAISE EXCEPTION 'VOTE_STALE';
    END IF;

    v_cooldown_hours := public.get_game_config_int('daily_pack_cooldown_hours', 12)::INTEGER;

    SELECT last_claim_at, last_consumed_topgg_vote_at
    INTO v_last, v_consumed
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account not found';
    END IF;

    IF v_consumed IS NOT NULL AND p_topgg_vote_at <= v_consumed THEN
        RAISE EXCEPTION 'VOTE_ALREADY_USED';
    END IF;

    IF v_last IS NOT NULL AND v_now < v_last + (v_cooldown_hours || ' hours')::INTERVAL THEN
        v_remaining := EXTRACT(EPOCH FROM (v_last + (v_cooldown_hours || ' hours')::INTERVAL - v_now))::INTEGER;
        RAISE EXCEPTION 'COOLDOWN:%', v_remaining;
    END IF;

    UPDATE public.players
    SET last_claim_at = v_now,
        last_consumed_topgg_vote_at = p_topgg_vote_at
    WHERE discord_id = p_club_id;

    FOR v_card IN
        SELECT * FROM jsonb_to_recordset(p_cards) AS x(
            name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
            pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
            potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
        )
    LOOP
        v_dob := COALESCE(
            v_card.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card.age, 25) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
        ) VALUES (
            p_club_id,
            v_card.name,
            v_card.position,
            v_card.rarity,
            v_card.base_rating,
            1,
            v_card.overall,
            COALESCE(v_card.pac, 50),
            COALESCE(v_card.sho, 50),
            COALESCE(v_card.pas, 50),
            COALESCE(v_card.dri, 50),
            COALESCE(v_card."def", 50),
            COALESCE(v_card.phy, 50),
            COALESCE(v_card.potential, v_card.base_potential, v_card.overall),
            COALESCE(v_card.base_potential, v_card.potential, v_card.overall),
            public.card_age_from_dob(v_dob),
            v_dob,
            COALESCE(NULLIF(trim(v_card.role), ''), 'Balanced')
        )
        RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
    END LOOP;

    v_result := jsonb_build_object(
        'card_ids', to_jsonb(v_ids),
        'claimed_at', to_jsonb(v_now),
        'vote_consumed_at', to_jsonb(p_topgg_vote_at)
    );

    IF p_idempotency_key IS NOT NULL THEN
        BEGIN
            INSERT INTO public.pack_claim_runs (idempotency_key, club_id, result_json)
            VALUES (p_idempotency_key, p_club_id, v_result);
        EXCEPTION
            WHEN unique_violation THEN
                SELECT result_json INTO v_prior
                FROM public.pack_claim_runs
                WHERE idempotency_key = p_idempotency_key;
                RETURN jsonb_build_object(
                    'status', 'already_applied',
                    'reason', NULL,
                    'data', COALESCE(v_prior, v_result)
                );
        END;
    END IF;

    RETURN jsonb_build_object(
        'status', 'applied',
        'reason', NULL,
        'data', v_result
    );
END;
$function$

CREATE OR REPLACE FUNCTION public.process_youth_intake(p_owner_id bigint, p_cards jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_week DATE;
    v_existing UUID[];
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_count INTEGER;
    v_dob DATE;
    v_pot INT;
    v_level INTEGER;
    v_cap INTEGER;
    v_used INTEGER;
    v_free INTEGER;
    v_seated INTEGER := 0;
    v_skipped INTEGER := 0;
    v_idx INTEGER := 0;
BEGIN
    IF p_cards IS NULL OR jsonb_array_length(p_cards) < 1 THEN
        RAISE EXCEPTION 'Intake must contain at least one card';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.players
        WHERE discord_id = p_owner_id AND COALESCE(is_ai, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Manager not found';
    END IF;

    v_week := public.current_intake_week();

    SELECT card_ids INTO v_existing
    FROM public.youth_intake_log
    WHERE owner_id = p_owner_id AND intake_week = v_week;

    IF v_existing IS NOT NULL THEN
        SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
        v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
        SELECT COUNT(*)::INTEGER INTO v_used
        FROM public.player_cards
        WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
        RETURN jsonb_build_object(
            'owner_id', p_owner_id,
            'intake_week', v_week,
            'card_ids', to_jsonb(v_existing),
            'seated', COALESCE(array_length(v_existing, 1), 0),
            'skipped', 0,
            'slots_used', COALESCE(v_used, 0),
            'slots_cap', v_cap,
            'already_processed', TRUE
        );
    END IF;

    v_count := public.get_game_config_int('youth_intake_count', 3)::INTEGER;
    IF jsonb_array_length(p_cards) > v_count THEN
        RAISE EXCEPTION 'Intake exceeds max cards (%)', v_count;
    END IF;

    SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
    v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.player_cards
    WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
    v_free := GREATEST(0, v_cap - COALESCE(v_used, 0));

    FOR v_card IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
    ) LOOP
        v_idx := v_idx + 1;
        IF v_seated >= v_free THEN
            v_skipped := v_skipped + 1;
            CONTINUE;
        END IF;

        v_pot := COALESCE(v_card.potential, v_card.base_potential);
        IF v_pot IS NULL THEN
            RAISE EXCEPTION 'Card % missing potential', v_card.name;
        END IF;
        IF v_pot < v_card.overall THEN
            v_pot := v_card.overall;
        END IF;

        v_dob := COALESCE(
            v_card.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card.age, 18) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
            in_academy, academy_progress, academy_seated_at
        ) VALUES (
            p_owner_id, v_card.name, v_card.position, v_card.rarity,
            v_card.base_rating, 1, v_card.overall,
            COALESCE(v_card.pac, 50), COALESCE(v_card.sho, 50),
            COALESCE(v_card.pas, 50), COALESCE(v_card.dri, 50),
            COALESCE(v_card.def, 50), COALESCE(v_card.phy, 50),
            v_pot,
            COALESCE(v_card.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob,
            COALESCE(NULLIF(trim(v_card.role), ''), 'Balanced'),
            TRUE, 0, NOW()
        ) RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
        v_seated := v_seated + 1;
    END LOOP;

    INSERT INTO public.youth_intake_log (owner_id, intake_week, card_ids)
    VALUES (p_owner_id, v_week, v_ids);

    RETURN jsonb_build_object(
        'owner_id', p_owner_id,
        'intake_week', v_week,
        'card_ids', to_jsonb(v_ids),
        'seated', v_seated,
        'skipped', v_skipped,
        'slots_used', COALESCE(v_used, 0) + v_seated,
        'slots_cap', v_cap,
        'already_processed', FALSE
    );
END;
$function$

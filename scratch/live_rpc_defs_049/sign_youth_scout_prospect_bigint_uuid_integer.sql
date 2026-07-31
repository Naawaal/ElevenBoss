CREATE OR REPLACE FUNCTION public.sign_youth_scout_prospect(p_owner_id bigint, p_report_id uuid, p_index integer)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_report RECORD;
    v_card JSONB;
    v_level INTEGER;
    v_cap INTEGER;
    v_used INTEGER;
    v_dob DATE;
    v_pot INT;
    v_card_id UUID;
BEGIN
    SELECT * INTO v_report
    FROM public.scouting_reports
    WHERE id = p_report_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Scout report not found';
    END IF;
    IF v_report.signed_card_id IS NOT NULL THEN
        RAISE EXCEPTION 'Report already signed';
    END IF;
    IF v_report.expires_at <= NOW() THEN
        RAISE EXCEPTION 'Report expired';
    END IF;
    IF p_index < 0 OR p_index > 2 THEN
        RAISE EXCEPTION 'Invalid prospect index';
    END IF;

    SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
    v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.player_cards
    WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
    IF COALESCE(v_used, 0) >= v_cap THEN
        RAISE EXCEPTION 'Academy slots full';
    END IF;

    v_card := v_report.prospects_json -> p_index;
    IF v_card IS NULL OR jsonb_typeof(v_card) <> 'object' THEN
        RAISE EXCEPTION 'Prospect missing';
    END IF;

    v_pot := COALESCE((v_card->>'potential')::INT, (v_card->>'base_potential')::INT);
    IF v_pot IS NULL THEN
        RAISE EXCEPTION 'Prospect missing potential';
    END IF;
    IF v_pot < COALESCE((v_card->>'overall')::INT, 0) THEN
        v_pot := (v_card->>'overall')::INT;
    END IF;

    v_dob := COALESCE(
        NULLIF(v_card->>'date_of_birth', '')::DATE,
        (CURRENT_DATE - (COALESCE((v_card->>'age')::INT, 18) || ' years')::INTERVAL)::DATE
    );

    INSERT INTO public.player_cards (
        owner_id, name, position, rarity, base_rating, level, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
        in_academy, academy_progress, academy_seated_at
    ) VALUES (
        p_owner_id,
        v_card->>'name',
        v_card->>'position',
        COALESCE(v_card->>'rarity', 'Common'),
        COALESCE((v_card->>'base_rating')::INT, (v_card->>'overall')::INT),
        1,
        (v_card->>'overall')::INT,
        COALESCE((v_card->>'pac')::INT, 50),
        COALESCE((v_card->>'sho')::INT, 50),
        COALESCE((v_card->>'pas')::INT, 50),
        COALESCE((v_card->>'dri')::INT, 50),
        COALESCE((v_card->>'def')::INT, 50),
        COALESCE((v_card->>'phy')::INT, 50),
        v_pot,
        COALESCE((v_card->>'base_potential')::INT, v_pot),
        public.card_age_from_dob(v_dob),
        v_dob,
        COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced'),
        TRUE, 0, NOW()
    ) RETURNING id INTO v_card_id;

    UPDATE public.scouting_reports
    SET signed_card_id = v_card_id
    WHERE id = p_report_id;

    PERFORM public.ensure_card_ownership_open(v_card_id, p_owner_id, 'youth_scout');

    RETURN jsonb_build_object(
        'card_id', v_card_id,
        'report_id', p_report_id,
        'index', p_index
    );
END;
$function$

-- 051: Persist archetype role on card intake (packs, register, youth, scouting)
-- player_cards.role already exists (003). scouting_pool_players needs role for regen → purchase.

ALTER TABLE public.scouting_pool_players
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'Balanced';

CREATE OR REPLACE FUNCTION register_new_player(
    p_discord_id BIGINT,
    p_username TEXT,
    p_club_name TEXT,
    p_manager_name TEXT,
    p_cards JSONB
) RETURNS VOID AS $$
DECLARE
    v_card_record RECORD;
    v_card_id UUID;
    v_slot INT := 1;
    v_pot INT;
    v_dob DATE;
BEGIN
    IF length(trim(p_club_name)) < 1 THEN
        RAISE EXCEPTION 'Club name cannot be empty';
    END IF;
    IF length(trim(p_manager_name)) < 1 THEN
        RAISE EXCEPTION 'Manager name cannot be empty';
    END IF;

    IF EXISTS (SELECT 1 FROM public.players WHERE discord_id = p_discord_id) THEN
        RAISE EXCEPTION 'ALREADY_REGISTERED';
    END IF;

    INSERT INTO players (
        discord_id, username, club_name, manager_name,
        coins, energy, max_energy, division
    ) VALUES (
        p_discord_id, p_username, trim(p_club_name), trim(p_manager_name),
        500, 100, 100, 'Grassroots'
    );

    INSERT INTO squads (discord_id, formation) VALUES (p_discord_id, '4-4-2');

    FOR v_card_record IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
    ) LOOP
        v_pot := COALESCE(v_card_record.potential, v_card_record.base_potential);
        IF v_pot IS NULL THEN
            RAISE EXCEPTION 'Card % missing potential', v_card_record.name;
        END IF;
        IF v_pot < v_card_record.overall THEN
            v_pot := v_card_record.overall;
        END IF;

        v_dob := COALESCE(
            v_card_record.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card_record.age, 25) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
        ) VALUES (
            p_discord_id, v_card_record.name, v_card_record.position, v_card_record.rarity,
            v_card_record.base_rating, 1, v_card_record.overall,
            COALESCE(v_card_record.pac, 50), COALESCE(v_card_record.sho, 50),
            COALESCE(v_card_record.pas, 50), COALESCE(v_card_record.dri, 50),
            COALESCE(v_card_record.def, 50), COALESCE(v_card_record.phy, 50),
            v_pot,
            COALESCE(v_card_record.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob,
            COALESCE(NULLIF(trim(v_card_record.role), ''), 'Balanced')
        ) RETURNING id INTO v_card_id;

        INSERT INTO squad_assignments (discord_id, player_card_id, position_slot)
        VALUES (p_discord_id, v_card_id, v_slot);

        v_slot := v_slot + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.claim_daily_pack(p_club_id BIGINT, p_cards JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_last TIMESTAMPTZ;
    v_now TIMESTAMPTZ := NOW();
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_remaining INTEGER;
    v_dob DATE;
BEGIN
    IF p_cards IS NULL OR jsonb_array_length(p_cards) < 1 THEN
        RAISE EXCEPTION 'Pack must contain at least one card';
    END IF;

    SELECT last_claim_at INTO v_last
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account not found';
    END IF;

    IF v_last IS NOT NULL AND v_now < v_last + INTERVAL '22 hours' THEN
        v_remaining := EXTRACT(EPOCH FROM (v_last + INTERVAL '22 hours' - v_now))::INTEGER;
        RAISE EXCEPTION 'COOLDOWN:%', v_remaining;
    END IF;

    UPDATE public.players SET last_claim_at = v_now WHERE discord_id = p_club_id;

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

    RETURN jsonb_build_object(
        'card_ids', to_jsonb(v_ids),
        'claimed_at', to_jsonb(v_now)
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.process_youth_intake(
    p_owner_id BIGINT,
    p_cards JSONB
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_week DATE;
    v_existing UUID[];
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_count INTEGER;
    v_dob DATE;
    v_pot INT;
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
        RETURN jsonb_build_object(
            'owner_id', p_owner_id,
            'intake_week', v_week,
            'card_ids', to_jsonb(v_existing),
            'already_processed', TRUE
        );
    END IF;

    v_count := public.get_game_config_int('youth_intake_count', 3)::INTEGER;
    IF jsonb_array_length(p_cards) > v_count THEN
        RAISE EXCEPTION 'Intake exceeds max cards (%)', v_count;
    END IF;

    FOR v_card IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
    ) LOOP
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
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
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
            COALESCE(NULLIF(trim(v_card.role), ''), 'Balanced')
        ) RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
    END LOOP;

    INSERT INTO public.youth_intake_log (owner_id, intake_week, card_ids)
    VALUES (p_owner_id, v_week, v_ids);

    RETURN jsonb_build_object(
        'owner_id', p_owner_id,
        'intake_week', v_week,
        'card_ids', to_jsonb(v_ids),
        'already_processed', FALSE
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.insert_scouting_pool_player(p_card JSONB)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_id UUID;
    v_source UUID;
    v_pot INT;
    v_dob DATE;
    v_max INTEGER;
BEGIN
    v_source := NULLIF(p_card->>'source_card_id', '')::UUID;
    IF v_source IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.scouting_pool_players WHERE source_card_id = v_source
    ) THEN
        SELECT id INTO v_id FROM public.scouting_pool_players WHERE source_card_id = v_source;
        RETURN v_id;
    END IF;

    v_max := public.get_game_config_int('scouting_pool_max_active', 50)::INTEGER;
    IF (SELECT COUNT(*) FROM public.scouting_pool_players WHERE claimed_by IS NULL) >= v_max THEN
        DELETE FROM public.scouting_pool_players
        WHERE id IN (
            SELECT id FROM public.scouting_pool_players
            WHERE claimed_by IS NULL
            ORDER BY created_at ASC
            LIMIT 1
        );
    END IF;

    v_pot := COALESCE((p_card->>'potential')::INT, (p_card->>'base_potential')::INT);
    v_dob := COALESCE((p_card->>'date_of_birth')::DATE, CURRENT_DATE - INTERVAL '18 years');

    INSERT INTO public.scouting_pool_players (
        source_card_id, name, position, rarity, base_rating, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, list_price, role
    ) VALUES (
        v_source,
        p_card->>'name',
        p_card->>'position',
        p_card->>'rarity',
        COALESCE((p_card->>'base_rating')::INT, (p_card->>'overall')::INT),
        (p_card->>'overall')::INT,
        COALESCE((p_card->>'pac')::INT, 50),
        COALESCE((p_card->>'sho')::INT, 50),
        COALESCE((p_card->>'pas')::INT, 50),
        COALESCE((p_card->>'dri')::INT, 50),
        COALESCE((p_card->>'def')::INT, 50),
        COALESCE((p_card->>'phy')::INT, 50),
        v_pot,
        COALESCE((p_card->>'base_potential')::INT, v_pot),
        COALESCE((p_card->>'age')::INT, public.card_age_from_dob(v_dob)),
        v_dob,
        COALESCE((p_card->>'list_price')::BIGINT, 500),
        COALESCE(NULLIF(trim(p_card->>'role'), ''), 'Balanced')
    ) RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.purchase_scouting_player(
    p_buyer_id BIGINT,
    p_pool_id UUID,
    p_expected_price BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_row RECORD;
    v_card_id UUID;
BEGIN
    PERFORM public.assert_not_in_match(p_buyer_id);

    SELECT * INTO v_row
    FROM public.scouting_pool_players
    WHERE id = p_pool_id AND claimed_by IS NULL
    FOR UPDATE;

    IF v_row IS NULL THEN
        RAISE EXCEPTION 'Scouting listing not found or already signed';
    END IF;

    IF p_expected_price IS DISTINCT FROM v_row.list_price THEN
        RAISE EXCEPTION 'Price mismatch (expected % coins)', v_row.list_price;
    END IF;

    PERFORM public.apply_club_economy(
        p_buyer_id,
        -v_row.list_price,
        0,
        'scouting_signing',
        'scouting:' || p_pool_id::TEXT,
        jsonb_build_object('pool_id', p_pool_id, 'price', v_row.list_price)
    );

    INSERT INTO public.player_cards (
        owner_id, name, position, rarity, base_rating, level, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
    ) VALUES (
        p_buyer_id, v_row.name, v_row.position, v_row.rarity,
        v_row.base_rating, 1, v_row.overall,
        v_row.pac, v_row.sho, v_row.pas, v_row.dri, v_row.def, v_row.phy,
        v_row.potential, v_row.base_potential, v_row.age, v_row.date_of_birth,
        COALESCE(NULLIF(trim(v_row.role), ''), 'Balanced')
    ) RETURNING id INTO v_card_id;

    UPDATE public.scouting_pool_players
    SET claimed_by = p_buyer_id, claimed_at = NOW()
    WHERE id = p_pool_id;

    RETURN jsonb_build_object(
        'pool_id', p_pool_id,
        'card_id', v_card_id,
        'coins_spent', v_row.list_price,
        'player_name', v_row.name
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION register_new_player(BIGINT, TEXT, TEXT, TEXT, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_daily_pack(BIGINT, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_youth_intake(BIGINT, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.insert_scouting_pool_player(JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.purchase_scouting_player(BIGINT, UUID, BIGINT)
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'player_cards' AND column_name = 'role'
    ) THEN
        RAISE EXCEPTION '051 guard failed: player_cards.role missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'scouting_pool_players' AND column_name = 'role'
    ) THEN
        RAISE EXCEPTION '051 guard failed: scouting_pool_players.role missing';
    END IF;
END;
$$;

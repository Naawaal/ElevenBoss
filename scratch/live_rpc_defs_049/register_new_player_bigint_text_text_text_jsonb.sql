CREATE OR REPLACE FUNCTION public.register_new_player(p_discord_id bigint, p_username text, p_club_name text, p_manager_name text, p_cards jsonb)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
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

    BEGIN
        INSERT INTO players (
            discord_id, username, club_name, manager_name,
            coins, energy, max_energy, action_energy, division,
            is_ai, identity_status, last_qualifying_activity_at, identity_status_changed_at
        ) VALUES (
            p_discord_id, p_username, trim(p_club_name), trim(p_manager_name),
            500, 120, 120, 120, 'Grassroots',
            FALSE, 'active', NOW(), NOW()
        );
    EXCEPTION
        WHEN unique_violation THEN
            RAISE EXCEPTION 'ALREADY_REGISTERED';
    END;

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
$function$

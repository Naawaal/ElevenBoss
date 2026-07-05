-- supabase/migrations/005_register_rpc.sql

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
BEGIN
    -- 1. Insert player record
    INSERT INTO players (
        discord_id,
        username,
        club_name,
        manager_name,
        coins,
        energy,
        max_energy,
        division
    ) VALUES (
        p_discord_id,
        p_username,
        p_club_name,
        p_manager_name,
        500,
        100,
        100,
        'Grassroots'
    );

    -- 2. Insert squad record
    INSERT INTO squads (
        discord_id,
        formation
    ) VALUES (
        p_discord_id,
        '4-4-2'
    );

    -- 3. Loop through cards list, insert player_cards and squad_assignments
    FOR v_card_record IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT) LOOP
        INSERT INTO player_cards (
            owner_id,
            name,
            position,
            rarity,
            base_rating,
            level,
            overall
        ) VALUES (
            p_discord_id,
            v_card_record.name,
            v_card_record.position,
            v_card_record.rarity,
            v_card_record.base_rating,
            1,
            v_card_record.overall
        ) RETURNING id INTO v_card_id;

        INSERT INTO squad_assignments (
            discord_id,
            player_card_id,
            position_slot
        ) VALUES (
            p_discord_id,
            v_card_id,
            v_slot
        );

        v_slot := v_slot + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

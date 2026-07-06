-- supabase/migrations/017_dynamic_potential.sql
-- Varied player potential: base_potential at creation, potential as current ceiling.

ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS base_potential INTEGER
        CHECK (base_potential IS NULL OR (base_potential >= 40 AND base_potential <= 99));

-- Backfill base_potential from legacy rows (potential was often stuck at default 85).
UPDATE public.player_cards
SET base_potential = potential
WHERE base_potential IS NULL AND potential IS NOT NULL;

-- Legacy backfill: recompute stuck-85 potentials from age/rarity/OVR.
UPDATE public.player_cards
SET
    potential = sub.new_pot,
    base_potential = sub.new_pot
FROM (
    SELECT
        id,
        GREATEST(
            40,
            LEAST(
                99,
                GREATEST(
                    overall,
                    LEAST(
                        CASE COALESCE(rarity, 'Common')
                            WHEN 'Legendary' THEN 99
                            WHEN 'Epic' THEN 92
                            WHEN 'Rare' THEN 85
                            ELSE 75
                        END,
                        overall + CASE
                            WHEN COALESCE(age, 25) <= 21 THEN 8 + (22 - COALESCE(age, 25))
                            WHEN COALESCE(age, 25) <= 27 THEN 5
                            WHEN COALESCE(age, 25) <= 32 THEN 2
                            ELSE 0
                        END
                    )
                )
            )
        ) AS new_pot
    FROM public.player_cards
    WHERE potential = 85 OR base_potential IS NULL
) AS sub
WHERE player_cards.id = sub.id;

UPDATE public.player_cards
SET base_potential = potential
WHERE base_potential IS NULL;

ALTER TABLE public.player_cards
    ALTER COLUMN potential DROP DEFAULT;

-- register_new_player: persist base_potential + require client-supplied potential
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
        potential INT, base_potential INT, age INT
    ) LOOP
        v_pot := COALESCE(v_card_record.potential, v_card_record.base_potential);
        IF v_pot IS NULL THEN
            RAISE EXCEPTION 'Card % missing potential', v_card_record.name;
        END IF;
        IF v_pot < v_card_record.overall THEN
            v_pot := v_card_record.overall;
        END IF;

        INSERT INTO player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age
        ) VALUES (
            p_discord_id, v_card_record.name, v_card_record.position, v_card_record.rarity,
            v_card_record.base_rating, 1, v_card_record.overall,
            COALESCE(v_card_record.pac, 50), COALESCE(v_card_record.sho, 50),
            COALESCE(v_card_record.pas, 50), COALESCE(v_card_record.dri, 50),
            COALESCE(v_card_record.def, 50), COALESCE(v_card_record.phy, 50),
            v_pot,
            COALESCE(v_card_record.base_potential, v_pot),
            COALESCE(v_card_record.age, 25)
        ) RETURNING id INTO v_card_id;

        INSERT INTO squad_assignments (discord_id, player_card_id, position_slot)
        VALUES (p_discord_id, v_card_id, v_slot);

        v_slot := v_slot + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

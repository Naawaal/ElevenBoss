-- 053: Retirement lifecycle fixes — full attrition curve, squad vacancy auto-promote, squad_invalid

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS squad_invalid BOOLEAN NOT NULL DEFAULT FALSE;

-- ---------------------------------------------------------------------------
-- retire_player_card: auto-promote same-role reserve or flag squad_invalid
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.retire_player_card(p_card_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
    v_slot INTEGER;
    v_formation TEXT;
    v_role TEXT;
    v_promoted UUID;
    v_xi_count INTEGER;
    v_invalid BOOLEAN;
BEGIN
    SELECT owner_id INTO v_owner
    FROM public.player_cards
    WHERE id = p_card_id AND COALESCE(is_retired, FALSE) = FALSE
    FOR UPDATE;

    IF v_owner IS NULL THEN
        RAISE EXCEPTION 'Card not found or already retired';
    END IF;

    SELECT position_slot INTO v_slot
    FROM public.squad_assignments
    WHERE player_card_id = p_card_id;

    DELETE FROM public.squad_assignments
    WHERE player_card_id = p_card_id;

    UPDATE public.player_cards
    SET is_retired = TRUE,
        retired_at = NOW()
    WHERE id = p_card_id;

    v_promoted := NULL;

    IF v_slot IS NOT NULL THEN
        SELECT formation INTO v_formation
        FROM public.squads
        WHERE discord_id = v_owner;

        v_role := public.formation_slot_role(COALESCE(v_formation, '4-4-2'), v_slot);

        SELECT pc.id INTO v_promoted
        FROM public.player_cards pc
        WHERE pc.owner_id = v_owner
          AND COALESCE(pc.is_retired, FALSE) = FALSE
          AND pc.position = v_role
          AND NOT EXISTS (
              SELECT 1 FROM public.squad_assignments sa
              WHERE sa.player_card_id = pc.id
          )
        ORDER BY pc.overall DESC, pc.id ASC
        LIMIT 1;

        IF v_promoted IS NOT NULL THEN
            INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
            VALUES (v_owner, v_slot, v_promoted);
        ELSE
            UPDATE public.players
            SET squad_invalid = TRUE
            WHERE discord_id = v_owner;
        END IF;
    END IF;

    SELECT COUNT(*) INTO v_xi_count
    FROM public.squad_assignments
    WHERE discord_id = v_owner;

    IF v_xi_count = 11 THEN
        UPDATE public.players
        SET squad_invalid = FALSE
        WHERE discord_id = v_owner;
    END IF;

    SELECT COALESCE(squad_invalid, FALSE) INTO v_invalid
    FROM public.players
    WHERE discord_id = v_owner;

    RETURN jsonb_build_object(
        'card_id', p_card_id,
        'owner_id', v_owner,
        'retired_at', NOW(),
        'vacated_slot', v_slot,
        'promoted_card_id', v_promoted,
        'squad_invalid', COALESCE(v_invalid, FALSE)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- process_season_aging: DRI@33+, SHO@35+ (full six-stat late career)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_season_aging()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_new_age INTEGER;
    v_old_age INTEGER;
    v_years INTEGER;
    v_i INTEGER;
    v_age_i INTEGER;
    v_retire_age INTEGER;
    v_warn_age INTEGER;
    v_retired INTEGER := 0;
    v_declined INTEGER := 0;
    v_warned INTEGER := 0;
    v_pac INTEGER;
    v_phy INTEGER;
    v_pas INTEGER;
    v_def INTEGER;
    v_dri INTEGER;
    v_sho INTEGER;
BEGIN
    v_retire_age := public.get_game_config_int('retirement_age', 36)::INTEGER;
    v_warn_age := public.get_game_config_int('retirement_warning_age', 35)::INTEGER;

    FOR v_card IN
        SELECT id, owner_id, age, date_of_birth, pac, phy, pas, def, dri, sho,
               retirement_notified_at, is_retired
        FROM public.player_cards
        WHERE COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE
    LOOP
        v_new_age := public.card_age_from_dob(v_card.date_of_birth);
        v_old_age := COALESCE(v_card.age, v_new_age);

        UPDATE public.player_cards SET age = v_new_age WHERE id = v_card.id;

        IF v_new_age >= v_warn_age AND v_card.retirement_notified_at IS NULL THEN
            UPDATE public.player_cards
            SET retirement_notified_at = NOW()
            WHERE id = v_card.id;
            v_warned := v_warned + 1;
        END IF;

        IF v_new_age > v_old_age THEN
            v_years := v_new_age - v_old_age;
            FOR v_i IN 1..v_years LOOP
                v_age_i := v_old_age + v_i;
                IF v_age_i >= 31 THEN
                    v_pac := GREATEST(1, v_card.pac - CASE WHEN v_age_i >= 35 THEN 2 ELSE 1 END);
                    v_phy := GREATEST(1, v_card.phy - CASE WHEN v_age_i >= 35 THEN 2 ELSE 1 END);
                    v_pas := v_card.pas;
                    v_def := v_card.def;
                    v_dri := v_card.dri;
                    v_sho := v_card.sho;
                    IF v_age_i >= 33 THEN
                        v_pas := GREATEST(1, v_card.pas - 1);
                        v_def := GREATEST(1, v_card.def - 1);
                        v_dri := GREATEST(1, v_card.dri - 1);
                    END IF;
                    IF v_age_i >= 35 THEN
                        v_sho := GREATEST(1, v_card.sho - 1);
                    END IF;
                    UPDATE public.player_cards
                    SET pac = v_pac, phy = v_phy, pas = v_pas, def = v_def,
                        dri = v_dri, sho = v_sho
                    WHERE id = v_card.id;
                    PERFORM public.recalculate_card_ovr(v_card.id);
                    v_declined := v_declined + 1;
                    SELECT pac, phy, pas, def, dri, sho
                    INTO v_card.pac, v_card.phy, v_card.pas, v_card.def, v_card.dri, v_card.sho
                    FROM public.player_cards WHERE id = v_card.id;
                END IF;
            END LOOP;
        END IF;

        IF v_new_age >= v_retire_age THEN
            PERFORM public.retire_player_card(v_card.id);
            v_retired := v_retired + 1;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'declined_cards', v_declined,
        'retired_cards', v_retired,
        'warned_cards', v_warned
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- set_formation_and_assignments: clear squad_invalid on full XI save
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_formation_and_assignments(
    p_discord_id BIGINT,
    p_formation TEXT,
    p_assignments JSONB
) RETURNS BOOLEAN AS $$
DECLARE
    v_row JSONB;
    v_slot INTEGER;
    v_card_id UUID;
    v_pos TEXT;
    v_count INTEGER := 0;
BEGIN
    PERFORM public.assert_not_in_match(p_discord_id);

    IF p_formation NOT IN ('4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '5-3-2') THEN
        RAISE EXCEPTION 'Invalid formation';
    END IF;

    FOR v_row IN SELECT * FROM jsonb_array_elements(p_assignments)
    LOOP
        v_slot := (v_row->>'slot')::INTEGER;
        v_card_id := (v_row->>'card_id')::UUID;
        SELECT position INTO v_pos
        FROM public.player_cards
        WHERE id = v_card_id AND owner_id = p_discord_id;
        IF v_pos IS NULL THEN
            RAISE EXCEPTION 'Assignment includes unowned or missing card';
        END IF;
        IF v_slot = 1 AND v_pos != 'GK' THEN
            RAISE EXCEPTION 'Slot 1 requires a goalkeeper';
        END IF;
        v_count := v_count + 1;
    END LOOP;

    UPDATE public.squads
    SET formation = p_formation, updated_at = NOW()
    WHERE discord_id = p_discord_id;

    DELETE FROM public.squad_assignments WHERE discord_id = p_discord_id;

    FOR v_row IN SELECT * FROM jsonb_array_elements(p_assignments)
    LOOP
        INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
        VALUES (
            p_discord_id,
            (v_row->>'slot')::INTEGER,
            (v_row->>'card_id')::UUID
        );
    END LOOP;

    IF v_count = 11 THEN
        UPDATE public.players
        SET squad_invalid = FALSE
        WHERE discord_id = p_discord_id;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

GRANT ALL PRIVILEGES ON FUNCTION public.retire_player_card(UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_season_aging() TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.set_formation_and_assignments(BIGINT, TEXT, JSONB) TO anon, authenticated, service_role;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'players' AND column_name = 'squad_invalid'
    ) THEN
        RAISE EXCEPTION '053 guard failed: players.squad_invalid missing';
    END IF;
    IF to_regprocedure('public.retire_player_card(uuid)') IS NULL THEN
        RAISE EXCEPTION '053 guard failed: retire_player_card missing';
    END IF;
    IF to_regprocedure('public.process_season_aging()') IS NULL THEN
        RAISE EXCEPTION '053 guard failed: process_season_aging missing';
    END IF;
    IF to_regprocedure('public.set_formation_and_assignments(bigint,text,jsonb)') IS NULL THEN
        RAISE EXCEPTION '053 guard failed: set_formation_and_assignments missing';
    END IF;
END;
$$;

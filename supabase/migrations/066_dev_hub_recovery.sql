-- 066_dev_hub_recovery.sql
-- Relocate active Recover: atomic batch RPC, no skill-drill slot consumption.

CREATE OR REPLACE FUNCTION public.process_recovery_batch(
    p_owner_id BIGINT,
    p_card_ids UUID[]
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_energy INTEGER;
    v_n INTEGER;
    v_cost_each INTEGER;
    v_grant INTEGER;
    v_total INTEGER;
    v_econ JSONB;
    v_players JSONB := '[]'::JSONB;
    v_card_id UUID;
    v_fatigue INTEGER;
    v_old_fatigue INTEGER;
    v_injury INTEGER;
    v_in_hospital BOOLEAN;
    v_in_academy BOOLEAN;
    v_gained INTEGER;
    v_seen UUID[] := ARRAY[]::UUID[];
BEGIN
    IF p_card_ids IS NULL THEN
        RAISE EXCEPTION 'Select between 1 and 3 players';
    END IF;

    v_n := cardinality(p_card_ids);
    IF v_n < 1 OR v_n > 3 THEN
        RAISE EXCEPTION 'Select between 1 and 3 players';
    END IF;

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        IF v_card_id = ANY (v_seen) THEN
            RAISE EXCEPTION 'Duplicate players in recovery selection';
        END IF;
        v_seen := array_append(v_seen, v_card_id);
    END LOOP;

    PERFORM public.sync_action_energy(p_owner_id);

    SELECT action_energy
    INTO v_energy
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    PERFORM public.assert_not_in_match(p_owner_id);

    v_cost_each := public.get_game_config_int('fatigue_recovery_energy', 5)::INTEGER;
    v_grant := public.get_game_config_int('fatigue_recovery_session', 40)::INTEGER;
    v_total := v_n * v_cost_each;

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        PERFORM public.assert_card_not_on_transfer_list(v_card_id);

        SELECT fatigue, injury_tier, COALESCE(in_hospital, FALSE), COALESCE(in_academy, FALSE)
        INTO v_fatigue, v_injury, v_in_hospital, v_in_academy
        FROM public.player_cards
        WHERE id = v_card_id
          AND owner_id = p_owner_id
          AND COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Player card not found or not owned';
        END IF;

        IF v_in_academy THEN
            RAISE EXCEPTION 'Player card not found or not owned';
        END IF;

        IF v_injury IS NOT NULL OR v_in_hospital THEN
            RAISE EXCEPTION 'Player is injured — use Hospital';
        END IF;

        IF v_fatigue >= 100 THEN
            RAISE EXCEPTION 'Player is already fully rested';
        END IF;

        IF EXISTS (
            SELECT 1 FROM public.active_evolutions
            WHERE card_id = v_card_id AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'Player is in an active evolution track';
        END IF;
    END LOOP;

    IF v_energy < v_total THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    v_econ := public.apply_club_economy(
        p_owner_id,
        0,
        -v_total,
        'recovery_batch',
        NULL,
        jsonb_build_object(
            'card_ids', to_jsonb(p_card_ids),
            'recovery_amount', v_grant,
            'player_count', v_n
        )
    );

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        SELECT fatigue INTO v_fatigue
        FROM public.player_cards
        WHERE id = v_card_id
        FOR UPDATE;

        v_old_fatigue := v_fatigue;
        v_fatigue := LEAST(100, v_fatigue + v_grant);
        v_gained := v_fatigue - v_old_fatigue;

        UPDATE public.player_cards
        SET fatigue = v_fatigue
        WHERE id = v_card_id;

        v_players := v_players || jsonb_build_array(
            jsonb_build_object(
                'card_id', v_card_id,
                'fatigue_gained', v_gained,
                'new_fatigue', v_fatigue
            )
        );
    END LOOP;

    RETURN jsonb_build_object(
        'energy_spent', v_total,
        'coins_spent', 0,
        'xp_gained', 0,
        'recovery_amount', v_grant,
        'players', v_players,
        'economy', v_econ
    );
END;
$$;

-- Thin single-card wrapper — no drill-slot side effects (supersedes 062 body).
CREATE OR REPLACE FUNCTION public.process_recovery_session(
    p_owner_id BIGINT,
    p_player_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_batch JSONB;
    v_player JSONB;
BEGIN
    v_batch := public.process_recovery_batch(p_owner_id, ARRAY[p_player_card_id]);
    v_player := v_batch -> 'players' -> 0;
    RETURN jsonb_build_object(
        'fatigue_gained', COALESCE((v_player ->> 'fatigue_gained')::INTEGER, 0),
        'new_fatigue', COALESCE((v_player ->> 'new_fatigue')::INTEGER, 0),
        'energy_spent', COALESCE((v_batch ->> 'energy_spent')::INTEGER, 0),
        'coins_spent', 0,
        'xp_gained', 0,
        'economy', v_batch -> 'economy'
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.process_recovery_batch(BIGINT, UUID[])
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_recovery_session(BIGINT, UUID)
    TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT;
BEGIN
    SELECT string_agg(req.obj, ', ')
    INTO v_missing
    FROM (
        VALUES
            ('function:process_recovery_batch'),
            ('function:process_recovery_session')
    ) AS req(obj)
    WHERE NOT (
        (req.obj = 'function:process_recovery_batch'
            AND to_regprocedure('public.process_recovery_batch(bigint,uuid[])') IS NOT NULL)
        OR (req.obj = 'function:process_recovery_session'
            AND to_regprocedure('public.process_recovery_session(bigint,uuid)') IS NOT NULL)
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 066 guard failed — missing: %', v_missing;
    END IF;
END;
$$;

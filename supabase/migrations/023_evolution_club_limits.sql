-- Evolution club pacing: max active cap, cold-start cooldown, start costs, hub status RPC.

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS last_evolution_started_at TIMESTAMPTZ;

COMMENT ON COLUMN public.players.last_evolution_started_at IS
    'Timestamp of last cold evolution start; replacement starts after cancel do not update this.';

CREATE OR REPLACE FUNCTION public.start_player_evolution(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_track_id TEXT
) RETURNS JSONB AS $$
DECLARE
    v_max_active CONSTANT INTEGER := 3;
    v_cooldown_hours CONSTANT INTEGER := 10;
    v_energy_cost CONSTANT INTEGER := 25;
    v_coin_multiplier CONSTANT INTEGER := 10;
    v_card RECORD;
    v_goal INTEGER;
    v_evo_id UUID;
    v_energy INTEGER;
    v_coins BIGINT;
    v_last_started TIMESTAMPTZ;
    v_active_count INTEGER;
    v_is_replacement BOOLEAN;
    v_cooldown_ends TIMESTAMPTZ;
    v_coin_cost BIGINT;
    v_ovr INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.sync_training_energy(p_owner_id);

    IF p_track_id NOT IN ('pace_boost', 'shooting_star', 'def_wall') THEN
        RAISE EXCEPTION 'Unknown evolution track';
    END IF;

    v_goal := 3;

    SELECT training_energy, coins, last_evolution_started_at
    INTO v_energy, v_coins, v_last_started
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    SELECT COUNT(*)::INTEGER INTO v_active_count
    FROM public.active_evolutions
    WHERE owner_id = p_owner_id AND status = 'active';

    IF v_active_count >= v_max_active THEN
        RAISE EXCEPTION 'You already have % evolutions in progress. Wait for one to complete or cancel an existing one.', v_max_active;
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE owner_id = p_owner_id
          AND status = 'cancelled'
          AND cancelled_at > COALESCE(v_last_started, '-infinity'::timestamptz)
    ) INTO v_is_replacement;

    IF NOT v_is_replacement AND v_last_started IS NOT NULL THEN
        v_cooldown_ends := v_last_started + (v_cooldown_hours || ' hours')::interval;
        IF NOW() < v_cooldown_ends THEN
            RAISE EXCEPTION 'Next evolution available in %',
                to_char(v_cooldown_ends - NOW(), 'FMHH24"h "FMMI"m"');
        END IF;
    END IF;

    SELECT id, owner_id, overall INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF v_card.id IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;

    v_ovr := v_card.overall;
    v_coin_cost := (v_coin_multiplier * v_ovr)::BIGINT;

    IF v_energy < v_energy_cost THEN
        RAISE EXCEPTION 'Insufficient training energy (% required)', v_energy_cost;
    END IF;
    IF v_coins < v_coin_cost THEN
        RAISE EXCEPTION 'Insufficient coins (% coins required)', v_coin_cost;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'This player is already evolving – complete or cancel the current track first';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND evolution_id = p_track_id AND status = 'completed'
    ) THEN
        RAISE EXCEPTION 'This player has already completed that evolution track';
    END IF;

    INSERT INTO public.active_evolutions (
        card_id, owner_id, evolution_id, target_metric,
        current_progress, target_goal, matches_played, matches_required,
        status, rewards_applied, started_at
    ) VALUES (
        p_card_id, p_owner_id, p_track_id, 'matches',
        0, v_goal, 0, v_goal,
        'active', FALSE, NOW()
    )
    RETURNING id INTO v_evo_id;

    UPDATE public.players
    SET
        training_energy = training_energy - v_energy_cost,
        coins = coins - v_coin_cost,
        last_evolution_started_at = CASE
            WHEN NOT v_is_replacement THEN NOW()
            ELSE last_evolution_started_at
        END
    WHERE discord_id = p_owner_id;

    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_owner_id, -v_coin_cost, 'coins', 'evolution_start');

    v_cooldown_ends := CASE
        WHEN v_is_replacement THEN v_last_started + (v_cooldown_hours || ' hours')::interval
        ELSE NOW() + (v_cooldown_hours || ' hours')::interval
    END;

    RETURN jsonb_build_object(
        'id', v_evo_id,
        'track_id', p_track_id,
        'matches_required', v_goal,
        'matches_played', 0,
        'is_replacement', v_is_replacement,
        'active_count', v_active_count + 1,
        'cooldown_ends_at', v_cooldown_ends,
        'energy_spent', v_energy_cost,
        'coins_spent', v_coin_cost
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.get_evolution_hub_status(p_owner_id BIGINT)
RETURNS JSONB AS $$
DECLARE
    v_max_active CONSTANT INTEGER := 3;
    v_cooldown_hours CONSTANT INTEGER := 10;
    v_energy_cost CONSTANT INTEGER := 25;
    v_coin_multiplier CONSTANT INTEGER := 10;
    v_last_started TIMESTAMPTZ;
    v_training_energy INTEGER;
    v_active_count INTEGER;
    v_is_replacement BOOLEAN;
    v_cooldown_ends TIMESTAMPTZ;
    v_cooldown_remaining INTEGER;
    v_can_cold_start BOOLEAN;
    v_active JSONB;
    v_history JSONB;
BEGIN
    PERFORM public.sync_training_energy(p_owner_id);

    SELECT last_evolution_started_at, training_energy
    INTO v_last_started, v_training_energy
    FROM public.players
    WHERE discord_id = p_owner_id;

    SELECT COUNT(*)::INTEGER INTO v_active_count
    FROM public.active_evolutions
    WHERE owner_id = p_owner_id AND status = 'active';

    SELECT EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE owner_id = p_owner_id
          AND status = 'cancelled'
          AND cancelled_at > COALESCE(v_last_started, '-infinity'::timestamptz)
    ) INTO v_is_replacement;

    IF v_last_started IS NULL THEN
        v_cooldown_ends := NULL;
        v_cooldown_remaining := 0;
        v_can_cold_start := v_active_count < v_max_active;
    ELSE
        v_cooldown_ends := v_last_started + (v_cooldown_hours || ' hours')::interval;
        IF NOW() >= v_cooldown_ends THEN
            v_cooldown_remaining := 0;
            v_can_cold_start := v_active_count < v_max_active;
        ELSE
            v_cooldown_remaining := GREATEST(0, EXTRACT(EPOCH FROM (v_cooldown_ends - NOW()))::INTEGER);
            v_can_cold_start := FALSE;
        END IF;
    END IF;

    SELECT COALESCE(jsonb_agg(row_to_json(t)::jsonb ORDER BY t.started_at DESC), '[]'::jsonb)
    INTO v_active
    FROM (
        SELECT
            e.id,
            e.card_id,
            e.evolution_id,
            e.matches_played,
            e.matches_required,
            e.current_progress,
            e.target_goal,
            e.started_at,
            pc.name AS card_name,
            pc.overall AS card_overall
        FROM public.active_evolutions e
        JOIN public.player_cards pc ON pc.id = e.card_id
        WHERE e.owner_id = p_owner_id AND e.status = 'active'
    ) t;

    SELECT COALESCE(jsonb_agg(row_to_json(t)::jsonb ORDER BY t.completed_at DESC), '[]'::jsonb)
    INTO v_history
    FROM (
        SELECT
            e.id,
            e.evolution_id,
            e.completed_at,
            pc.name AS card_name
        FROM public.active_evolutions e
        JOIN public.player_cards pc ON pc.id = e.card_id
        WHERE e.owner_id = p_owner_id AND e.status = 'completed'
        ORDER BY e.completed_at DESC
        LIMIT 5
    ) t;

    RETURN jsonb_build_object(
        'active_count', v_active_count,
        'max_active', v_max_active,
        'slots_label', v_active_count::TEXT || '/' || v_max_active::TEXT || ' slots used',
        'last_evolution_started_at', v_last_started,
        'cooldown_ends_at', v_cooldown_ends,
        'cooldown_remaining_seconds', v_cooldown_remaining,
        'can_cold_start', v_can_cold_start,
        'can_replace', v_is_replacement AND v_active_count < v_max_active,
        'can_start', (v_can_cold_start OR (v_is_replacement AND v_active_count < v_max_active)),
        'training_energy', v_training_energy,
        'start_energy_cost', v_energy_cost,
        'start_coin_multiplier', v_coin_multiplier,
        'active', v_active,
        'recent_completed', v_history
    );
END;
$$ LANGUAGE plpgsql;

GRANT ALL PRIVILEGES ON FUNCTION public.start_player_evolution TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.get_evolution_hub_status TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.players.last_evolution_started_at'),
            ('function:public.get_evolution_hub_status')
    ) AS req(obj)
    WHERE NOT (
        (
            req.obj LIKE 'column:%'
            AND EXISTS (
                SELECT 1
                FROM information_schema.columns c
                WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (
            req.obj LIKE 'function:%'
            AND to_regprocedure('public.get_evolution_hub_status(bigint)') IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 023 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;

    RAISE NOTICE 'Migration 023 evolution club limits OK';
END $$;

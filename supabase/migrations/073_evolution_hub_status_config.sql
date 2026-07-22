-- 073_evolution_hub_status_config.sql
-- Align get_evolution_hub_status cooldown/slots/costs with game_config
-- (same keys/defaults as start_player_evolution). Fixes false Start-button
-- lockout when hub used hardcoded 10h while start used seeded 6h.

CREATE OR REPLACE FUNCTION public.get_evolution_hub_status(p_owner_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_active INTEGER;
    v_cooldown_hours INTEGER;
    v_energy_cost INTEGER;
    v_flat INTEGER;
    v_ovr_mult INTEGER;
    v_energy_max INTEGER;
    v_last_started TIMESTAMPTZ;
    v_action_energy INTEGER;
    v_active_count INTEGER;
    v_is_replacement BOOLEAN;
    v_cooldown_ends TIMESTAMPTZ;
    v_cooldown_remaining INTEGER;
    v_can_cold_start BOOLEAN;
    v_active JSONB;
    v_history JSONB;
BEGIN
    PERFORM public.sync_action_energy(p_owner_id);

    v_max_active := public.get_game_config_int('evolution_max_active', 3)::INTEGER;
    v_cooldown_hours := public.get_game_config_int('evolution_cooldown_hours', 10)::INTEGER;
    v_energy_cost := public.get_game_config_int('evolution_start_energy', 25)::INTEGER;
    v_flat := public.get_game_config_int('evolution_start_flat', 500)::INTEGER;
    v_ovr_mult := public.get_game_config_int('evolution_start_ovr_mult', 5)::INTEGER;
    v_energy_max := public.get_game_config_int('energy_max', 120)::INTEGER;

    SELECT last_evolution_started_at, action_energy
    INTO v_last_started, v_action_energy
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
        -- dual-write era: training_energy alias keeps existing cog readers working
        'training_energy', v_action_energy,
        'action_energy', v_action_energy,
        'max_energy', v_energy_max,
        'start_energy_cost', v_energy_cost,
        'start_coin_flat', v_flat,
        'start_coin_ovr_mult', v_ovr_mult,
        'start_coin_multiplier', v_ovr_mult,
        'active', v_active,
        'recent_completed', v_history
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.get_evolution_hub_status(BIGINT) TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('function:public.get_evolution_hub_status')
    ) AS req(obj)
    WHERE NOT (
        req.obj LIKE 'function:%'
        AND to_regprocedure('public.get_evolution_hub_status(bigint)') IS NOT NULL
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '073_evolution_hub_status_config schema guard failed: missing %', v_missing;
    END IF;
END;
$$;

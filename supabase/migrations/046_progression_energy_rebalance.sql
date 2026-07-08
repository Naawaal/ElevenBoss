-- US-35: Progression & Energy Rebalance (v2.x)
-- - Tune energy regen + bot energy cost
-- - Boost drill base XP values
-- - Make evolution cooldown and max-active configurable via game_config

-- ---------------------------------------------------------------------------
-- Seed / update game_config keys (idempotent)
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('energy_regen_per_min', '0.25'),           -- 1 energy per 4 minutes (15/hour)
    ('match_energy_bot', '15'),
    ('drill_basic_xp', '50'),
    ('drill_advanced_xp', '120'),
    ('evolution_cooldown_hours', '6'),
    ('evolution_max_active', '4')
ON CONFLICT (key) DO UPDATE
SET value_json = EXCLUDED.value_json,
    updated_at = NOW();

-- ---------------------------------------------------------------------------
-- start_player_evolution — config-driven cooldown + slot cap
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.start_player_evolution(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_track_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_active INTEGER;
    v_cooldown_hours INTEGER;
    v_energy_cost INTEGER;
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
    v_min_level INTEGER;
    v_econ JSONB;
    v_flat BIGINT;
    v_ovr_mult INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.sync_action_energy(p_owner_id);

    v_max_active := public.get_game_config_int('evolution_max_active', 3)::INTEGER;
    v_cooldown_hours := public.get_game_config_int('evolution_cooldown_hours', 10)::INTEGER;

    v_energy_cost := public.get_game_config_int('evolution_start_energy', 25)::INTEGER;
    v_flat := public.get_game_config_int('evolution_start_flat', 500);
    v_ovr_mult := public.get_game_config_int('evolution_start_ovr_mult', 5)::INTEGER;

    IF p_track_id NOT IN ('pace_boost', 'shooting_star', 'def_wall') THEN
        RAISE EXCEPTION 'Unknown evolution track';
    END IF;

    v_min_level := CASE p_track_id
        WHEN 'pace_boost' THEN 5
        WHEN 'shooting_star' THEN 10
        WHEN 'def_wall' THEN 8
        ELSE 1
    END;

    v_goal := 3;

    SELECT action_energy, coins, last_evolution_started_at
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

    SELECT id, owner_id, overall, level INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF v_card.id IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;

    IF v_card.level < v_min_level THEN
        RAISE EXCEPTION 'Player level too low for this evolution (requires level %)', v_min_level;
    END IF;

    v_ovr := v_card.overall;
    v_coin_cost := (v_flat + v_ovr_mult * v_ovr)::BIGINT;

    IF v_energy < v_energy_cost THEN
        RAISE EXCEPTION 'Insufficient action energy (% required)', v_energy_cost;
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

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_coin_cost,
        -v_energy_cost,
        'evolution_start',
        NULL,
        jsonb_build_object('card_id', p_card_id, 'track_id', p_track_id, 'evo_id', v_evo_id)
    );

    UPDATE public.players
    SET last_evolution_started_at = NOW()
    WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object(
        'evo_id', v_evo_id,
        'coin_cost', v_coin_cost,
        'energy_cost', v_energy_cost,
        'economy', v_econ
    );
END;
$$;


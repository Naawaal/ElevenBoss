-- Enforce POT ceiling and 99 stat cap on stat drills and evolution rewards.
-- Aligns process_stat_drill with fodder_training (already blocks at potential).

CREATE OR REPLACE FUNCTION public.process_stat_drill(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_drill_id TEXT
) RETURNS JSONB AS $$
DECLARE
    v_coins BIGINT;
    v_energy INTEGER;
    v_daily INTEGER;
    v_reset DATE;
    v_stat_col TEXT;
    v_ovr INTEGER;
    v_potential INTEGER;
    v_old_stat INTEGER;
    v_new_stat INTEGER;
    v_new_ovr INTEGER;
    v_cost BIGINT;
    v_levels INTEGER;
    v_daily_limit INTEGER := 20;
BEGIN
    PERFORM public.sync_training_energy(p_owner_id);

    SELECT training_energy, coins, daily_drill_count, daily_drill_reset_at
    INTO v_energy, v_coins, v_daily, v_reset
    FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;

    PERFORM public.assert_not_in_match(p_owner_id);

    IF v_daily >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily drill limit reached';
    END IF;
    IF v_energy < 15 THEN
        RAISE EXCEPTION 'Insufficient training energy';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.player_cards WHERE id = p_card_id AND owner_id = p_owner_id
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Player is in an active evolution track';
    END IF;

    v_stat_col := CASE p_drill_id
        WHEN 'pac_sprint' THEN 'pac'
        WHEN 'sho_finishing' THEN 'sho'
        WHEN 'pas_distribution' THEN 'pas'
        WHEN 'dri_dribble' THEN 'dri'
        WHEN 'def_tackling' THEN 'def'
        WHEN 'phy_strength' THEN 'phy'
        ELSE NULL
    END;
    IF v_stat_col IS NULL THEN
        RAISE EXCEPTION 'Unknown drill type';
    END IF;

    EXECUTE format(
        'SELECT overall, potential, %I FROM public.player_cards WHERE id = $1 FOR UPDATE',
        v_stat_col
    ) INTO v_ovr, v_potential, v_old_stat USING p_card_id;

    IF v_old_stat >= 99 THEN
        RAISE EXCEPTION 'Stat is already at maximum';
    END IF;

    IF v_ovr >= v_potential THEN
        RAISE EXCEPTION 'Player is already at maximum overall for their potential';
    END IF;

    v_cost := (5 * v_ovr)::BIGINT;
    IF v_coins < v_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    v_new_stat := v_old_stat + 1;
    v_levels := 1;
    EXECUTE format(
        'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
        v_stat_col
    ) USING v_new_stat, p_card_id;

    v_new_ovr := public.recalculate_card_ovr(p_card_id);

    UPDATE public.players
    SET training_energy = training_energy - 15,
        coins = coins - v_cost,
        daily_drill_count = daily_drill_count + 1
    WHERE discord_id = p_owner_id;

    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_owner_id, -v_cost, 'coins', 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'stat', upper(v_stat_col),
        'levels_gained', v_levels,
        'new_ovr', v_new_ovr,
        'coins_spent', v_cost
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.claim_evolution_reward(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_card_id UUID;
    v_evo_id TEXT;
    v_progress INTEGER;
    v_goal INTEGER;
    v_stat_col TEXT;
    v_reward INTEGER;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_applied INTEGER;
    v_status TEXT;
    v_overall INTEGER;
    v_potential INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.card_id, e.evolution_id,
           COALESCE(e.matches_played, e.current_progress),
           COALESCE(e.matches_required, e.target_goal),
           e.status
    INTO v_card_id, v_evo_id, v_progress, v_goal, v_status
    FROM public.active_evolutions e
    JOIN public.player_cards c ON c.id = e.card_id
    WHERE e.id = p_evo_id AND c.owner_id = p_owner_id
    FOR UPDATE;

    IF v_card_id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
    END IF;
    IF v_status <> 'active' THEN
        RAISE EXCEPTION 'Evolution is not active';
    END IF;
    IF v_progress < v_goal THEN
        RAISE EXCEPTION 'Evolution not complete';
    END IF;

    SELECT overall, potential
    INTO v_overall, v_potential
    FROM public.player_cards
    WHERE id = v_card_id
    FOR UPDATE;

    v_stat_col := CASE v_evo_id
        WHEN 'pace_boost' THEN 'pac'
        WHEN 'shooting_star' THEN 'sho'
        WHEN 'def_wall' THEN 'def'
        ELSE 'pac'
    END;
    v_reward := 5;

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1',
        v_stat_col
    ) INTO v_current USING v_card_id;

    IF v_overall >= v_potential OR v_current >= 99 THEN
        v_applied := 0;
        v_new_val := v_current;
    ELSE
        v_new_val := LEAST(99, v_current + v_reward);
        v_applied := v_new_val - v_current;
        IF v_applied > 0 THEN
            EXECUTE format(
                'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
                v_stat_col
            ) USING v_new_val, v_card_id;
        END IF;
    END IF;

    v_new_ovr := public.recalculate_card_ovr(v_card_id);

    UPDATE public.active_evolutions
    SET
        status = 'completed',
        rewards_applied = TRUE,
        completed_at = NOW()
    WHERE id = p_evo_id;

    RETURN jsonb_build_object(
        'new_ovr', v_new_ovr,
        'stat', upper(v_stat_col),
        'reward', v_applied,
        'new_value', v_new_val,
        'blocked_by_cap', (v_overall >= v_potential AND v_current < 99)
    );
END;
$$ LANGUAGE plpgsql;

GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_evolution_reward TO anon, authenticated, service_role;

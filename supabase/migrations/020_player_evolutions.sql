-- Evolution lifecycle: status tracking, RPC guards, friendly-match progress hook.

ALTER TABLE public.active_evolutions
    ADD COLUMN IF NOT EXISTS owner_id BIGINT REFERENCES public.players(discord_id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS matches_required INTEGER,
    ADD COLUMN IF NOT EXISTS matches_played INTEGER,
    ADD COLUMN IF NOT EXISTS rewards_applied BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

UPDATE public.active_evolutions e
SET
    owner_id = pc.owner_id,
    matches_required = COALESCE(e.matches_required, e.target_goal),
    matches_played = COALESCE(e.matches_played, e.current_progress),
    started_at = COALESCE(e.started_at, e.created_at),
    status = COALESCE(NULLIF(e.status, ''), 'active')
FROM public.player_cards pc
WHERE pc.id = e.card_id;

ALTER TABLE public.active_evolutions
    DROP CONSTRAINT IF EXISTS active_evolutions_status_check;
ALTER TABLE public.active_evolutions
    ADD CONSTRAINT active_evolutions_status_check
    CHECK (status IN ('active', 'completed', 'cancelled'));

DROP INDEX IF EXISTS idx_active_evolutions_card_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_evolutions_active_card
    ON public.active_evolutions(card_id)
    WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS idx_active_evolutions_completed_track
    ON public.active_evolutions(card_id, evolution_id)
    WHERE status = 'completed';

CREATE INDEX IF NOT EXISTS idx_active_evolutions_owner_status
    ON public.active_evolutions(owner_id, status);

-- Shared progress tick (bot/league via process_match_result, friendly via direct call)
CREATE OR REPLACE FUNCTION public.tick_evolution_match_progress(p_card_ids UUID[])
RETURNS JSONB AS $$
DECLARE
    v_card_id UUID;
    v_rows JSONB := '[]'::JSONB;
    v_row RECORD;
BEGIN
    IF p_card_ids IS NULL OR array_length(p_card_ids, 1) IS NULL THEN
        RETURN '[]'::JSONB;
    END IF;

    FOREACH v_card_id IN ARRAY p_card_ids LOOP
        UPDATE public.active_evolutions
        SET
            matches_played = LEAST(
                COALESCE(matches_required, target_goal),
                COALESCE(matches_played, current_progress) + 1
            ),
            current_progress = LEAST(
                target_goal,
                current_progress + 1
            )
        WHERE card_id = v_card_id
          AND status = 'active'
          AND target_metric = 'matches';

        FOR v_row IN
            SELECT
                e.id,
                e.card_id,
                e.evolution_id,
                e.owner_id,
                COALESCE(e.matches_played, e.current_progress) AS played,
                COALESCE(e.matches_required, e.target_goal) AS required
            FROM public.active_evolutions e
            WHERE e.card_id = v_card_id AND e.status = 'active'
        LOOP
            v_rows := v_rows || jsonb_build_array(to_jsonb(v_row));
        END LOOP;
    END LOOP;

    RETURN v_rows;
END;
$$ LANGUAGE plpgsql;

-- process_match_result overload fix: see 021_process_match_result_overload_fix.sql

CREATE OR REPLACE FUNCTION public.start_player_evolution(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_track_id TEXT
) RETURNS JSONB AS $$
DECLARE
    v_card RECORD;
    v_goal INTEGER;
    v_evo_id UUID;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    IF p_track_id NOT IN ('pace_boost', 'shooting_star', 'def_wall') THEN
        RAISE EXCEPTION 'Unknown evolution track';
    END IF;

    v_goal := CASE p_track_id
        WHEN 'pace_boost' THEN 3
        WHEN 'shooting_star' THEN 3
        WHEN 'def_wall' THEN 3
        ELSE 3
    END;

    SELECT id, owner_id, overall INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF v_card.id IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
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

    RETURN jsonb_build_object(
        'id', v_evo_id,
        'track_id', p_track_id,
        'matches_required', v_goal,
        'matches_played', 0
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.cancel_player_evolution(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_evo RECORD;
    v_coins BIGINT;
    v_fee CONSTANT INTEGER := 100;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.id, e.card_id, e.owner_id, e.status
    INTO v_evo
    FROM public.active_evolutions e
    WHERE e.id = p_evo_id AND e.owner_id = p_owner_id
    FOR UPDATE;

    IF v_evo.id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
    END IF;
    IF v_evo.status <> 'active' THEN
        RAISE EXCEPTION 'Only active evolutions can be cancelled';
    END IF;

    SELECT coins INTO v_coins FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;
    IF v_coins < v_fee THEN
        RAISE EXCEPTION 'Insufficient coins for cancellation fee (% coins required)', v_fee;
    END IF;

    UPDATE public.players SET coins = coins - v_fee WHERE discord_id = p_owner_id;
    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_owner_id, -v_fee, 'coins', 'evolution_cancel');

    UPDATE public.active_evolutions
    SET
        status = 'cancelled',
        cancelled_at = NOW(),
        matches_played = 0,
        current_progress = 0
    WHERE id = p_evo_id;

    RETURN jsonb_build_object('cancelled', TRUE, 'fee', v_fee);
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

    v_stat_col := CASE v_evo_id
        WHEN 'pace_boost' THEN 'pac'
        WHEN 'shooting_star' THEN 'sho'
        WHEN 'def_wall' THEN 'def'
        ELSE 'pac'
    END;
    v_reward := 5;

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1 FOR UPDATE',
        v_stat_col
    ) INTO v_current USING v_card_id;

    v_new_val := LEAST(99, v_current + v_reward);
    v_applied := v_new_val - v_current;

    IF v_applied > 0 THEN
        EXECUTE format(
            'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
            v_stat_col
        ) USING v_new_val, v_card_id;
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
        'new_value', v_new_val
    );
END;
$$ LANGUAGE plpgsql;

-- Guards: only block *active* evolutions (completed history rows are OK)
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
    v_ovr NUMERIC;
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
        'SELECT overall, %I FROM public.player_cards WHERE id = $1 FOR UPDATE',
        v_stat_col
    ) INTO v_ovr, v_old_stat USING p_card_id;

    v_cost := (5 * v_ovr)::BIGINT;
    IF v_coins < v_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    IF v_old_stat >= 99 THEN
        v_levels := 0;
        v_new_stat := 99;
    ELSE
        v_new_stat := v_old_stat + 1;
        v_levels := 1;
        EXECUTE format(
            'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
            v_stat_col
        ) USING v_new_stat, p_card_id;
    END IF;

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

GRANT ALL PRIVILEGES ON FUNCTION public.tick_evolution_match_progress TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.start_player_evolution TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.cancel_player_evolution TO anon, authenticated, service_role;

-- Sale/fusion guards: only active evolutions block the card
CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
) RETURNS BIGINT AS $$
DECLARE
    v_sale_value BIGINT;
    v_ovr NUMERIC;
    v_rarity TEXT;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);

    SELECT overall, rarity INTO v_ovr, v_rarity
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_club_id
    FOR UPDATE;

    IF v_ovr IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE discord_id = p_club_id AND player_card_id = p_card_id
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in your starting 11';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in active training';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in an active evolution';
    END IF;

    v_sale_value := public.compute_agent_offer(v_ovr, v_rarity);

    DELETE FROM public.player_cards WHERE id = p_card_id;

    UPDATE public.players
    SET coins = coins + v_sale_value
    WHERE discord_id = p_club_id;

    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_club_id, v_sale_value, 'coins', 'agent_sale');

    RETURN v_sale_value;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.train_with_fodder(
    p_owner_id BIGINT,
    p_target_id UUID,
    p_fodder_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_target_owner BIGINT;
    v_fodder_owner BIGINT;
    v_target_level INTEGER;
    v_target_rarity TEXT;
    v_target_overall INTEGER;
    v_target_cap INTEGER;
    v_target_pos TEXT;
    v_stat_col TEXT;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT owner_id, level, rarity, overall, position
    INTO v_target_owner, v_target_level, v_target_rarity, v_target_overall, v_target_pos
    FROM public.player_cards
    WHERE id = p_target_id
    FOR UPDATE;

    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN
        RAISE EXCEPTION 'Target player card not found or not owned by you';
    END IF;

    SELECT owner_id INTO v_fodder_owner
    FROM public.player_cards
    WHERE id = p_fodder_id
    FOR UPDATE;

    IF v_fodder_owner IS NULL OR v_fodder_owner != p_owner_id THEN
        RAISE EXCEPTION 'Fodder player card not found or not owned by you';
    END IF;

    IF p_target_id = p_fodder_id THEN
        RAISE EXCEPTION 'Cannot use the same card as both target and fodder';
    END IF;

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_fodder_id) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in your starting 11';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_fodder_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in active training';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_fodder_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in an active evolution';
    END IF;

    v_target_cap := CASE v_target_rarity
        WHEN 'Common' THEN 75
        WHEN 'Rare' THEN 84
        WHEN 'Epic' THEN 90
        ELSE 99
    END;

    IF v_target_overall >= LEAST(v_target_cap, (
        SELECT potential FROM public.player_cards WHERE id = p_target_id
    )) THEN
        RAISE EXCEPTION 'Target player is already at maximum overall for their potential';
    END IF;

    DELETE FROM public.player_cards WHERE id = p_fodder_id;

    v_stat_col := CASE v_target_pos
        WHEN 'FWD' THEN 'sho'
        WHEN 'DEF' THEN 'def'
        WHEN 'GK' THEN 'def'
        ELSE 'pas'
    END;

    EXECUTE format(
        'UPDATE public.player_cards SET level = level + 1, %I = LEAST(99, %I + 1) WHERE id = $1',
        v_stat_col, v_stat_col
    ) USING p_target_id;

    PERFORM public.recalculate_card_ovr(p_target_id);

    INSERT INTO public.player_xp_log (card_id, xp_amount, source)
    VALUES (p_target_id, 100, 'fodder_training');

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

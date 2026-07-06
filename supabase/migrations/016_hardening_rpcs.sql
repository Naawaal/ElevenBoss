-- supabase/migrations/016_hardening_rpcs.sql
-- US-22 / Task Group 15: hardened RPCs

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.assert_not_in_match(p_discord_id BIGINT)
RETURNS VOID AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.match_locks WHERE discord_id = p_discord_id) THEN
        RAISE EXCEPTION 'Manager is locked in an active match';
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.compute_agent_offer(p_ovr INTEGER, p_rarity TEXT)
RETURNS BIGINT AS $$
DECLARE
    v_calc_ovr INTEGER := GREATEST(45, p_ovr);
    v_base NUMERIC;
    v_mult NUMERIC := 1.0;
BEGIN
    v_base := power(v_calc_ovr - 45, 2.5) * 1.5 + 50;
    v_mult := CASE p_rarity
        WHEN 'Rare' THEN 1.5
        WHEN 'Epic' THEN 2.2
        WHEN 'Legendary' THEN 3.5
        ELSE 1.0
    END;
    RETURN GREATEST(0, floor(v_base * v_mult))::BIGINT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION public.recalculate_card_ovr(p_card_id UUID)
RETURNS INTEGER AS $$
DECLARE
    v_pos TEXT;
    v_pac INTEGER; v_sho INTEGER; v_pas INTEGER; v_dri INTEGER;
    v_def INTEGER; v_phy INTEGER; v_potential INTEGER;
    v_wpac NUMERIC; v_wsho NUMERIC; v_wpas NUMERIC;
    v_wdri NUMERIC; v_wdef NUMERIC; v_wphy NUMERIC;
    v_bonus INTEGER := 0;
    v_base NUMERIC;
    v_ovr INTEGER;
    v_ps TEXT;
BEGIN
    SELECT position, pac, sho, pas, dri, def, phy, potential
    INTO v_pos, v_pac, v_sho, v_pas, v_dri, v_def, v_phy, v_potential
    FROM public.player_cards
    WHERE id = p_card_id;

    IF v_pos IS NULL THEN
        RAISE EXCEPTION 'Card not found';
    END IF;

    v_wpac := 0.10; v_wsho := 0.15; v_wpas := 0.25; v_wdri := 0.20; v_wdef := 0.15; v_wphy := 0.15;
    IF v_pos = 'FWD' THEN
        v_wpac := 0.20; v_wsho := 0.35; v_wpas := 0.10; v_wdri := 0.20; v_wdef := 0.05; v_wphy := 0.10;
    ELSIF v_pos = 'DEF' THEN
        v_wpac := 0.15; v_wsho := 0.05; v_wpas := 0.10; v_wdri := 0.05; v_wdef := 0.40; v_wphy := 0.25;
    ELSIF v_pos = 'GK' THEN
        v_wpac := 0.15; v_wsho := 0.00; v_wpas := 0.15; v_wdri := 0.00; v_wdef := 0.50; v_wphy := 0.20;
    END IF;

    FOR v_ps IN
        SELECT playstyle_key FROM public.player_playstyles WHERE card_id = p_card_id
    LOOP
        IF (v_ps = 'Power Header' AND v_pos IN ('FWD', 'DEF'))
            OR (v_ps = 'Playmaker' AND v_pos = 'MID')
            OR (v_ps = 'Speedster' AND v_pos IN ('FWD', 'MID', 'DEF')) THEN
            v_bonus := v_bonus + 1;
        END IF;
    END LOOP;
    v_bonus := LEAST(v_bonus, 2);

    v_base := (
        v_pac * v_wpac + v_sho * v_wsho + v_pas * v_wpas +
        v_dri * v_wdri + v_def * v_wdef + v_phy * v_wphy
    );
    v_ovr := LEAST(floor(v_base + v_bonus)::INTEGER, v_potential);

    UPDATE public.player_cards SET overall = v_ovr WHERE id = p_card_id;
    RETURN v_ovr;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Training energy + stat drills
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.sync_training_energy(p_club_id BIGINT)
RETURNS JSONB AS $$
DECLARE
    v_energy INTEGER;
    v_updated_at TIMESTAMPTZ;
    v_daily INTEGER;
    v_reset DATE;
    v_hours NUMERIC;
    v_regen INTEGER;
    v_daily_limit INTEGER := 20;
BEGIN
    SELECT training_energy, training_energy_updated_at, daily_drill_count, daily_drill_reset_at
    INTO v_energy, v_updated_at, v_daily, v_reset
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF v_energy IS NULL THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    IF v_reset < CURRENT_DATE THEN
        v_daily := 0;
        v_reset := CURRENT_DATE;
    END IF;

    v_hours := EXTRACT(EPOCH FROM (NOW() - v_updated_at)) / 3600.0;
    IF v_hours > 0 AND v_energy < 100 THEN
        v_regen := floor(v_hours * 25)::INTEGER;
        v_energy := LEAST(100, v_energy + v_regen);
        v_updated_at := NOW();
    END IF;

    UPDATE public.players
    SET training_energy = v_energy,
        training_energy_updated_at = v_updated_at,
        daily_drill_count = v_daily,
        daily_drill_reset_at = v_reset
    WHERE discord_id = p_club_id;

    RETURN jsonb_build_object(
        'training_energy', v_energy,
        'daily_drill_count', v_daily,
        'daily_drill_limit', v_daily_limit
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.process_stat_drill(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_drill_id TEXT
) RETURNS JSONB AS $$
DECLARE
    v_stat_col TEXT;
    v_energy INTEGER;
    v_coins BIGINT;
    v_daily INTEGER;
    v_reset DATE;
    v_ovr INTEGER;
    v_cost BIGINT;
    v_old_stat INTEGER;
    v_new_stat INTEGER;
    v_levels INTEGER := 0;
    v_new_ovr INTEGER;
    v_daily_limit INTEGER := 20;
BEGIN
    PERFORM public.sync_training_energy(p_owner_id);

    SELECT training_energy, coins, daily_drill_count, daily_drill_reset_at
    INTO v_energy, v_coins, v_daily, v_reset
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

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

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_card_id) THEN
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

-- ---------------------------------------------------------------------------
-- Agent sale (server-priced)
-- ---------------------------------------------------------------------------

DROP FUNCTION IF EXISTS public.process_agent_sale(BIGINT, UUID, BIGINT);

CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
) RETURNS BIGINT AS $$
DECLARE
    v_ovr INTEGER;
    v_rarity TEXT;
    v_sale_value BIGINT;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);

    SELECT overall, rarity INTO v_ovr, v_rarity
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_club_id
    FOR UPDATE;

    IF v_ovr IS NULL THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_card_id) THEN
        RAISE EXCEPTION 'Cannot sell a player in your starting 11';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in active training';
    END IF;

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_card_id) THEN
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

-- ---------------------------------------------------------------------------
-- Fodder fusion (OVR via recalculate)
-- ---------------------------------------------------------------------------

DROP FUNCTION IF EXISTS public.train_with_fodder(BIGINT, UUID, UUID);

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

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_fodder_id) THEN
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

-- ---------------------------------------------------------------------------
-- Squad mutations
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.swap_squad_players(
    p_discord_id BIGINT,
    p_slot INTEGER,
    p_reserve_card_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_starter_id UUID;
    v_reserve_pos TEXT;
BEGIN
    PERFORM public.assert_not_in_match(p_discord_id);

    IF p_slot < 1 OR p_slot > 11 THEN
        RAISE EXCEPTION 'Invalid squad slot';
    END IF;

    SELECT position INTO v_reserve_pos
    FROM public.player_cards
    WHERE id = p_reserve_card_id AND owner_id = p_discord_id
    FOR UPDATE;

    IF v_reserve_pos IS NULL THEN
        RAISE EXCEPTION 'Reserve player not found or not owned';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE discord_id = p_discord_id AND player_card_id = p_reserve_card_id
    ) THEN
        RAISE EXCEPTION 'Reserve player is already in the starting 11';
    END IF;

    IF p_slot = 1 AND v_reserve_pos != 'GK' THEN
        RAISE EXCEPTION 'Slot 1 requires a goalkeeper';
    END IF;

    SELECT player_card_id INTO v_starter_id
    FROM public.squad_assignments
    WHERE discord_id = p_discord_id AND position_slot = p_slot
    FOR UPDATE;

    IF v_starter_id IS NULL THEN
        RAISE EXCEPTION 'No starter assigned to that slot';
    END IF;

    DELETE FROM public.squad_assignments
    WHERE discord_id = p_discord_id AND position_slot = p_slot;

    INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
    VALUES (p_discord_id, p_slot, p_reserve_card_id);

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

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

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Skills & evolutions
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.allocate_skill_point(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_stat TEXT
) RETURNS JSONB AS $$
DECLARE
    v_col TEXT;
    v_points INTEGER;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    v_col := CASE lower(p_stat)
        WHEN 'pac' THEN 'pac'
        WHEN 'sho' THEN 'sho'
        WHEN 'pas' THEN 'pas'
        WHEN 'dri' THEN 'dri'
        WHEN 'def' THEN 'def'
        WHEN 'phy' THEN 'phy'
        ELSE NULL
    END;
    IF v_col IS NULL THEN
        RAISE EXCEPTION 'Invalid stat';
    END IF;

    EXECUTE format(
        'SELECT skill_points, %I FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',
        v_col
    ) INTO v_points, v_current USING p_card_id, p_owner_id;

    IF v_points IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;
    IF v_points <= 0 THEN
        RAISE EXCEPTION 'No skill points available';
    END IF;
    IF v_current >= 99 THEN
        RAISE EXCEPTION 'Stat already at maximum';
    END IF;

    v_new_val := v_current + 1;
    EXECUTE format(
        'UPDATE public.player_cards SET %I = $1, skill_points = skill_points - 1 WHERE id = $2',
        v_col
    ) USING v_new_val, p_card_id;

    v_new_ovr := public.recalculate_card_ovr(p_card_id);

    RETURN jsonb_build_object('new_ovr', v_new_ovr, 'stat', upper(v_col), 'new_value', v_new_val);
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
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.card_id, e.evolution_id, e.current_progress, e.target_goal
    INTO v_card_id, v_evo_id, v_progress, v_goal
    FROM public.active_evolutions e
    JOIN public.player_cards c ON c.id = e.card_id
    WHERE e.id = p_evo_id AND c.owner_id = p_owner_id
    FOR UPDATE;

    IF v_card_id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
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

    IF v_current + v_reward > 99 THEN
        RAISE EXCEPTION 'Evolution reward would exceed stat cap';
    END IF;

    v_new_val := v_current + v_reward;
    EXECUTE format(
        'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
        v_stat_col
    ) USING v_new_val, v_card_id;

    v_new_ovr := public.recalculate_card_ovr(v_card_id);
    DELETE FROM public.active_evolutions WHERE id = p_evo_id;

    RETURN jsonb_build_object(
        'new_ovr', v_new_ovr,
        'stat', upper(v_stat_col),
        'reward', v_reward
    );
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Registration idempotency
-- ---------------------------------------------------------------------------

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
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT, potential INT, age INT
    ) LOOP
        INSERT INTO player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, age
        ) VALUES (
            p_discord_id, v_card_record.name, v_card_record.position, v_card_record.rarity,
            v_card_record.base_rating, 1, v_card_record.overall,
            COALESCE(v_card_record.pac, 50), COALESCE(v_card_record.sho, 50),
            COALESCE(v_card_record.pas, 50), COALESCE(v_card_record.dri, 50),
            COALESCE(v_card_record.def, 50), COALESCE(v_card_record.phy, 50),
            COALESCE(v_card_record.potential, 85), COALESCE(v_card_record.age, 25)
        ) RETURNING id INTO v_card_id;

        INSERT INTO squad_assignments (discord_id, player_card_id, position_slot)
        VALUES (p_discord_id, v_card_id, v_slot);

        v_slot := v_slot + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

GRANT ALL PRIVILEGES ON FUNCTION public.assert_not_in_match TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.compute_agent_offer TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.recalculate_card_ovr TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.sync_training_energy TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.swap_squad_players TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.set_formation_and_assignments TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.allocate_skill_point TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_evolution_reward TO anon, authenticated, service_role;

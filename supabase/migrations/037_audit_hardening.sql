-- 037: Audit hardening — drill daily reset, swap/fusion guards, match XP idempotency

-- ---------------------------------------------------------------------------
-- Formation slot role helper (mirrors packages/match_engine/formation_positions.py)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.formation_slot_role(p_formation TEXT, p_slot INTEGER)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_slot < 1 OR p_slot > 11 THEN 'DEF'
        WHEN p_formation = '4-4-2' THEN
            (ARRAY['GK','DEF','DEF','DEF','DEF','MID','MID','MID','MID','FWD','FWD'])[p_slot]
        WHEN p_formation = '4-3-3' THEN
            (ARRAY['GK','DEF','DEF','DEF','DEF','MID','MID','MID','FWD','FWD','FWD'])[p_slot]
        WHEN p_formation = '4-2-3-1' THEN
            (ARRAY['GK','DEF','DEF','DEF','DEF','MID','MID','MID','MID','MID','FWD'])[p_slot]
        WHEN p_formation = '3-5-2' THEN
            (ARRAY['GK','DEF','DEF','DEF','MID','MID','MID','MID','MID','FWD','FWD'])[p_slot]
        WHEN p_formation = '5-3-2' THEN
            (ARRAY['GK','DEF','DEF','DEF','DEF','DEF','MID','MID','MID','FWD','FWD'])[p_slot]
        ELSE
            (ARRAY['GK','DEF','DEF','DEF','DEF','MID','MID','MID','MID','FWD','FWD'])[p_slot]
    END;
$$;

-- ---------------------------------------------------------------------------
-- Squad swap: enforce formation slot role (not just GK in slot 1)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.swap_squad_players(
    p_discord_id BIGINT,
    p_slot INTEGER,
    p_reserve_card_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_starter_id UUID;
    v_reserve_pos TEXT;
    v_formation TEXT;
    v_required_role TEXT;
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

    SELECT formation INTO v_formation
    FROM public.squads
    WHERE discord_id = p_discord_id;

    v_required_role := public.formation_slot_role(COALESCE(v_formation, '4-4-2'), p_slot);

    IF v_reserve_pos != v_required_role THEN
        RAISE EXCEPTION 'Player position % does not match slot requirement %', v_reserve_pos, v_required_role;
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

-- ---------------------------------------------------------------------------
-- Drills: restore lazy daily club drill reset (regression from 028)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_stat_drill(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_drill_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_coins BIGINT;
    v_energy INTEGER;
    v_daily INTEGER;
    v_reset DATE;
    v_ovr INTEGER;
    v_card_level INTEGER;
    v_cost BIGINT;
    v_daily_limit INTEGER := 20;
    v_drill_energy INTEGER;
    v_drill_min_level INTEGER := 1;
    v_drill_xp_base INTEGER;
    v_drill_flat BIGINT;
    v_drill_ovr_mult INTEGER;
    v_advanced_min INTEGER;
    v_xp_gain INTEGER;
    v_xp_result JSONB;
    v_player_drill_count INTEGER;
    v_player_drill_cap CONSTANT INTEGER := 5;
    v_econ JSONB;
BEGIN
    PERFORM public.sync_action_energy(p_owner_id);

    SELECT coins, action_energy, daily_drill_count, daily_drill_reset_at
    INTO v_coins, v_energy, v_daily, v_reset
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    PERFORM public.assert_not_in_match(p_owner_id);

    IF v_reset < CURRENT_DATE THEN
        v_daily := 0;
        v_reset := CURRENT_DATE;
    END IF;

    IF v_daily >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily drill limit reached';
    END IF;

    IF p_drill_id NOT IN (
        'pac_sprint', 'sho_finishing', 'pas_distribution',
        'dri_dribble', 'def_tackling', 'phy_strength'
    ) THEN
        RAISE EXCEPTION 'Unknown drill type';
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

    SELECT overall, level
    INTO v_ovr, v_card_level
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    v_advanced_min := public.get_game_config_int('drill_advanced_min_level', 10)::INTEGER;

    IF v_card_level >= v_advanced_min THEN
        v_drill_flat := public.get_game_config_int('drill_advanced_flat', 300);
        v_drill_ovr_mult := public.get_game_config_int('drill_advanced_ovr_mult', 3)::INTEGER;
        v_drill_energy := public.get_game_config_int('drill_advanced_energy', 15)::INTEGER;
        v_drill_xp_base := public.get_game_config_int('drill_advanced_xp', 80)::INTEGER;
        v_drill_min_level := v_advanced_min;
    ELSE
        v_drill_flat := public.get_game_config_int('drill_basic_flat', 100);
        v_drill_ovr_mult := public.get_game_config_int('drill_basic_ovr_mult', 2)::INTEGER;
        v_drill_energy := public.get_game_config_int('drill_basic_energy', 10)::INTEGER;
        v_drill_xp_base := public.get_game_config_int('drill_basic_xp', 30)::INTEGER;
    END IF;

    IF v_card_level < v_drill_min_level THEN
        RAISE EXCEPTION 'Player level too low for this drill (requires level %)', v_drill_min_level;
    END IF;

    INSERT INTO public.player_drill_daily_log (card_id, drill_date, count)
    VALUES (p_card_id, CURRENT_DATE, 1)
    ON CONFLICT (card_id, drill_date)
    DO UPDATE SET count = player_drill_daily_log.count + 1
    RETURNING count INTO v_player_drill_count;

    IF v_player_drill_count > v_player_drill_cap THEN
        RAISE EXCEPTION 'Daily drill limit reached for this player (max % per day)', v_player_drill_cap;
    END IF;

    IF v_energy < v_drill_energy THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    v_cost := (v_drill_flat + v_drill_ovr_mult * v_ovr)::BIGINT;
    IF v_coins < v_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    v_xp_gain := GREATEST(
        1,
        floor(
            v_drill_xp_base::NUMERIC
            / (1.0 + 0.05 * GREATEST(0, v_card_level - 1))
        )::INTEGER
    );

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_cost,
        -v_drill_energy,
        'stat_drill_' || p_drill_id,
        NULL,
        jsonb_build_object('card_id', p_card_id, 'drill_id', p_drill_id, 'cost', v_cost)
    );

    UPDATE public.players
    SET daily_drill_count = v_daily + 1,
        daily_drill_reset_at = v_reset
    WHERE discord_id = p_owner_id;

    v_xp_result := public.apply_card_xp(p_card_id, v_xp_gain, 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'xp_gain', v_xp_gain,
        'cost', v_cost,
        'daily_drill_count', v_daily + 1,
        'daily_drill_limit', v_daily_limit,
        'economy', v_econ,
        'progression', v_xp_result
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Fusion: block target card in starting XI
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.train_with_fodder(
    p_owner_id BIGINT,
    p_target_id UUID,
    p_fodder_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_target_owner BIGINT;
    v_fodder_owner BIGINT;
    v_fodder_level INTEGER;
    v_fodder_overall INTEGER;
    v_target_overall INTEGER;
    v_target_potential INTEGER;
    v_fusion_xp INTEGER;
    v_fusion_count INTEGER;
    v_fusion_limit CONSTANT INTEGER := 3;
    v_fusion_cost BIGINT;
    v_coins BIGINT;
    v_xp_result JSONB;
    v_econ JSONB;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.sync_action_energy(p_owner_id);

    v_fusion_cost := public.get_game_config_int('fusion_coins', 200);

    SELECT coins INTO v_coins
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF v_coins < v_fusion_cost THEN
        RAISE EXCEPTION 'Insufficient coins (% coins required for fusion)', v_fusion_cost;
    END IF;

    SELECT owner_id, overall, potential
    INTO v_target_owner, v_target_overall, v_target_potential
    FROM public.player_cards
    WHERE id = p_target_id
    FOR UPDATE;

    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN
        RAISE EXCEPTION 'Target player card not found or not owned by you';
    END IF;

    SELECT owner_id, level, overall
    INTO v_fodder_owner, v_fodder_level, v_fodder_overall
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

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_target_id) THEN
        RAISE EXCEPTION 'Cannot upgrade a player card that is currently in your starting 11';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_fodder_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in active training';
    END IF;

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_fodder_id AND status = 'active') THEN
        RAISE EXCEPTION 'Cannot burn a player card that is currently in an active evolution';
    END IF;

    IF EXISTS (SELECT 1 FROM public.active_evolutions WHERE card_id = p_target_id AND status = 'active') THEN
        RAISE EXCEPTION 'Cannot upgrade a player card that is currently in an active evolution';
    END IF;

    INSERT INTO public.fusion_daily_log (club_id, fusion_date, count)
    VALUES (p_owner_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, fusion_date)
    DO UPDATE SET count = fusion_daily_log.count + 1
    RETURNING count INTO v_fusion_count;

    IF v_fusion_count > v_fusion_limit THEN
        RAISE EXCEPTION 'Daily fusion limit reached (max % per day)', v_fusion_limit;
    END IF;

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_fusion_cost,
        0,
        'fusion',
        NULL,
        jsonb_build_object('target_id', p_target_id, 'fodder_id', p_fodder_id)
    );

    v_fusion_xp := 50
        + (GREATEST(1, v_fodder_level) * 8)
        + (GREATEST(0, v_fodder_overall) * 2);

    DELETE FROM public.player_cards WHERE id = p_fodder_id;

    v_xp_result := public.apply_card_xp(p_target_id, v_fusion_xp, 'fusion');

    RETURN jsonb_build_object(
        'fusion_xp', v_fusion_xp,
        'fusion_cost', v_fusion_cost,
        'levels_gained', COALESCE((v_xp_result->>'levels_gained')::INTEGER, 0),
        'skill_points_granted', COALESCE((v_xp_result->>'skill_points_granted')::INTEGER, 0),
        'new_level', COALESCE((v_xp_result->>'new_level')::INTEGER, 1),
        'new_ovr', v_target_overall,
        'xp_wasted', COALESCE((v_xp_result->>'xp_wasted')::INTEGER, 0),
        'economy', v_econ
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Match XP idempotency: track per-history-row XP application
-- ---------------------------------------------------------------------------
ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES public.match_runs(id) ON DELETE SET NULL;

ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS xp_applied_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_match_history_player_run
    ON public.match_history(player_id, run_id)
    WHERE run_id IS NOT NULL;

UPDATE public.match_history
SET xp_applied_at = created_at
WHERE xp_applied_at IS NULL;

GRANT ALL PRIVILEGES ON FUNCTION public.formation_slot_role(TEXT, INTEGER) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.match_history.run_id'),
            ('column:public.match_history.xp_applied_at'),
            ('function:formation_slot_role'),
            ('function:swap_squad_players'),
            ('function:process_stat_drill'),
            ('function:train_with_fodder')
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
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'formation_slot_role' THEN to_regprocedure('public.formation_slot_role(text,integer)')
                WHEN 'swap_squad_players' THEN to_regprocedure('public.swap_squad_players(bigint,integer,uuid)')
                WHEN 'process_stat_drill' THEN to_regprocedure('public.process_stat_drill(bigint,uuid,text)')
                WHEN 'train_with_fodder' THEN to_regprocedure('public.train_with_fodder(bigint,uuid,uuid)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 037 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

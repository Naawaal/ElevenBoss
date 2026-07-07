-- US-25: Economy v2 — game_config, unified action energy, apply_club_economy

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.game_config (
    key         TEXT PRIMARY KEY,
    value_json  JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  BIGINT
);

ALTER TABLE public.economy_ledger
    ADD COLUMN IF NOT EXISTS reason_meta JSONB,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS economy_ledger_idempotency_key_uidx
    ON public.economy_ledger (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS action_energy INT,
    ADD COLUMN IF NOT EXISTS action_energy_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_daily_login DATE,
    ADD COLUMN IF NOT EXISTS login_streak INT NOT NULL DEFAULT 0;

UPDATE public.players
SET
    action_energy = LEAST(100, GREATEST(COALESCE(energy, 0), COALESCE(training_energy, 0))),
    action_energy_updated_at = COALESCE(action_energy_updated_at, NOW())
WHERE action_energy IS NULL;

ALTER TABLE public.players
    ALTER COLUMN action_energy SET DEFAULT 100;

CREATE TABLE IF NOT EXISTS public.agent_sale_daily_log (
    club_id   BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    sale_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (club_id, sale_date)
);

CREATE TABLE IF NOT EXISTS public.energy_refill_daily_log (
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    refill_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count       INT NOT NULL DEFAULT 0,
    PRIMARY KEY (club_id, refill_date)
);

-- ---------------------------------------------------------------------------
-- Seed game_config (idempotent)
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('economy_v2_enabled', 'true'),
    ('match_bot_win', '200'),
    ('match_bot_draw', '100'),
    ('match_bot_loss', '50'),
    ('match_friendly_win', '150'),
    ('match_league_win_min', '300'),
    ('match_league_win_max', '500'),
    ('daily_login_base', '100'),
    ('daily_login_streak_bonus', '10'),
    ('daily_login_streak_cap', '50'),
    ('agent_sale_daily_cap', '10'),
    ('drill_basic_flat', '100'),
    ('drill_basic_ovr_mult', '2'),
    ('drill_basic_energy', '10'),
    ('drill_basic_xp', '30'),
    ('drill_advanced_min_level', '10'),
    ('drill_advanced_flat', '300'),
    ('drill_advanced_ovr_mult', '3'),
    ('drill_advanced_energy', '15'),
    ('drill_advanced_xp', '80'),
    ('evolution_start_flat', '500'),
    ('evolution_start_ovr_mult', '5'),
    ('evolution_start_energy', '25'),
    ('fusion_coins', '200'),
    ('energy_regen_per_min', '0.1666667'),
    ('energy_max', '100'),
    ('energy_refill_amount', '50'),
    ('energy_refill_costs', '[200, 400, 600]'),
    ('match_energy_bot', '20'),
    ('match_energy_friendly', '15'),
    ('match_energy_league', '10')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_game_config(p_key TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_val JSONB;
BEGIN
    SELECT value_json INTO v_val FROM public.game_config WHERE key = p_key;
    RETURN v_val;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_game_config_int(p_key TEXT, p_default BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_val JSONB;
BEGIN
    v_val := public.get_game_config(p_key);
    IF v_val IS NULL THEN
        RETURN p_default;
    END IF;
    RETURN (v_val #>> '{}')::BIGINT;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_game_config_numeric(p_key TEXT, p_default NUMERIC)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_val JSONB;
BEGIN
    v_val := public.get_game_config(p_key);
    IF v_val IS NULL THEN
        RETURN p_default;
    END IF;
    RETURN (v_val #>> '{}')::NUMERIC;
END;
$$;

CREATE OR REPLACE FUNCTION public.economy_v2_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE((public.get_game_config('economy_v2_enabled') #>> '{}')::BOOLEAN, FALSE);
$$;

CREATE OR REPLACE FUNCTION public.league_division_tier(p_division TEXT)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE COALESCE(p_division, 'Grassroots')
        WHEN 'Grassroots' THEN 0
        WHEN 'Amateur' THEN 1
        WHEN 'Semi-Pro' THEN 2
        WHEN 'Professional' THEN 3
        WHEN 'Elite' THEN 4
        WHEN 'Legendary' THEN 5
        ELSE 0
    END;
$$;

CREATE OR REPLACE FUNCTION public.league_match_coins(p_division TEXT)
RETURNS BIGINT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_min BIGINT;
    v_max BIGINT;
    v_tier INTEGER;
BEGIN
    v_min := public.get_game_config_int('match_league_win_min', 300);
    v_max := public.get_game_config_int('match_league_win_max', 500);
    v_tier := public.league_division_tier(p_division);
    RETURN v_min + ((v_max - v_min) * v_tier / 5);
END;
$$;

-- ---------------------------------------------------------------------------
-- Action energy (unified pool)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.sync_action_energy(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_energy INTEGER;
    v_max INTEGER;
    v_updated_at TIMESTAMPTZ;
    v_regen_per_min NUMERIC;
    v_minutes NUMERIC;
    v_regen INTEGER;
BEGIN
    v_max := public.get_game_config_int('energy_max', 100)::INTEGER;
    v_regen_per_min := public.get_game_config_numeric('energy_regen_per_min', 0.1666667);

    SELECT action_energy, action_energy_updated_at
    INTO v_energy, v_updated_at
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    v_energy := COALESCE(v_energy, v_max);
    v_updated_at := COALESCE(v_updated_at, NOW());

    v_minutes := EXTRACT(EPOCH FROM (NOW() - v_updated_at)) / 60.0;
    IF v_minutes > 0 AND v_energy < v_max THEN
        v_regen := floor(v_minutes * v_regen_per_min)::INTEGER;
        v_energy := LEAST(v_max, v_energy + v_regen);
    END IF;

    UPDATE public.players
    SET
        action_energy = v_energy,
        action_energy_updated_at = NOW(),
        energy = v_energy,
        training_energy = v_energy
    WHERE discord_id = p_club_id;

    RETURN jsonb_build_object(
        'action_energy', v_energy,
        'max_energy', v_max,
        'regen_per_min', v_regen_per_min
    );
END;
$$;

-- ponytail: legacy alias — drills/evolutions call sync_training_energy today
CREATE OR REPLACE FUNCTION public.sync_training_energy(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN public.sync_action_energy(p_club_id);
END;
$$;

-- ---------------------------------------------------------------------------
-- apply_club_economy — single coin + action-energy write path
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.apply_club_economy(
    p_club_id BIGINT,
    p_coin_delta BIGINT,
    p_energy_delta INTEGER,
    p_source TEXT,
    p_idempotency_key TEXT DEFAULT NULL,
    p_meta JSONB DEFAULT '{}'::JSONB
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_existing RECORD;
    v_coins BIGINT;
    v_energy INTEGER;
    v_max INTEGER;
    v_new_coins BIGINT;
    v_new_energy INTEGER;
BEGIN
    IF p_idempotency_key IS NOT NULL THEN
        SELECT club_id, amount, source, reason_meta
        INTO v_existing
        FROM public.economy_ledger
        WHERE idempotency_key = p_idempotency_key;

        IF FOUND THEN
            RETURN jsonb_build_object(
                'replay', TRUE,
                'club_id', v_existing.club_id,
                'coin_delta', v_existing.amount,
                'source', v_existing.source,
                'meta', COALESCE(v_existing.reason_meta, '{}'::JSONB)
            );
        END IF;
    END IF;

    PERFORM public.sync_action_energy(p_club_id);

    SELECT coins, action_energy
    INTO v_coins, v_energy
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    v_max := public.get_game_config_int('energy_max', 100)::INTEGER;
    v_new_coins := v_coins + COALESCE(p_coin_delta, 0);
    v_new_energy := v_energy + COALESCE(p_energy_delta, 0);

    IF v_new_coins < 0 THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;
    IF v_new_energy < 0 THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;
    IF v_new_energy > v_max THEN
        v_new_energy := v_max;
    END IF;

    UPDATE public.players
    SET
        coins = v_new_coins,
        action_energy = v_new_energy,
        action_energy_updated_at = NOW(),
        energy = v_new_energy,
        training_energy = v_new_energy
    WHERE discord_id = p_club_id;

    IF COALESCE(p_coin_delta, 0) <> 0 THEN
        INSERT INTO public.economy_ledger (
            club_id, amount, currency, source, reason_meta, idempotency_key
        ) VALUES (
            p_club_id,
            p_coin_delta,
            'coins',
            p_source,
            COALESCE(p_meta, '{}'::JSONB),
            p_idempotency_key
        );
    ELSIF p_idempotency_key IS NOT NULL THEN
        INSERT INTO public.economy_ledger (
            club_id, amount, currency, source, reason_meta, idempotency_key
        ) VALUES (
            p_club_id,
            0,
            'coins',
            p_source,
            COALESCE(p_meta, '{}'::JSONB) || jsonb_build_object('energy_delta', p_energy_delta),
            p_idempotency_key
        );
    END IF;

    RETURN jsonb_build_object(
        'replay', FALSE,
        'club_id', p_club_id,
        'coins', v_new_coins,
        'action_energy', v_new_energy,
        'coin_delta', COALESCE(p_coin_delta, 0),
        'energy_delta', COALESCE(p_energy_delta, 0),
        'source', p_source
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Daily login + energy refill
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.claim_daily_login(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_last DATE;
    v_streak INTEGER;
    v_base BIGINT;
    v_bonus BIGINT;
    v_cap BIGINT;
    v_reward BIGINT;
    v_result JSONB;
BEGIN
    SELECT last_daily_login, login_streak
    INTO v_last, v_streak
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    IF v_last = CURRENT_DATE THEN
        RAISE EXCEPTION 'Daily login reward already claimed today';
    END IF;

    v_base := public.get_game_config_int('daily_login_base', 100);
    v_bonus := public.get_game_config_int('daily_login_streak_bonus', 10);
    v_cap := public.get_game_config_int('daily_login_streak_cap', 50);

    IF v_last = CURRENT_DATE - 1 THEN
        v_streak := COALESCE(v_streak, 0) + 1;
    ELSE
        v_streak := 1;
    END IF;

    v_reward := v_base + LEAST(v_cap, GREATEST(0, v_streak - 1) * v_bonus);

    UPDATE public.players
    SET last_daily_login = CURRENT_DATE, login_streak = v_streak
    WHERE discord_id = p_club_id;

    v_result := public.apply_club_economy(
        p_club_id,
        v_reward,
        0,
        'daily_login',
        'daily_login:' || p_club_id::TEXT || ':' || CURRENT_DATE::TEXT,
        jsonb_build_object('streak', v_streak, 'reward', v_reward)
    );

    RETURN v_result || jsonb_build_object('streak', v_streak, 'reward', v_reward);
END;
$$;

CREATE OR REPLACE FUNCTION public.purchase_energy_refill(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
    v_costs JSONB;
    v_cost BIGINT;
    v_refill_amt INTEGER;
    v_idx INTEGER;
BEGIN
    PERFORM public.sync_action_energy(p_club_id);

    INSERT INTO public.energy_refill_daily_log (club_id, refill_date, count)
    VALUES (p_club_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, refill_date)
    DO UPDATE SET count = energy_refill_daily_log.count + 1
    RETURNING count INTO v_count;

    IF v_count > 3 THEN
        RAISE EXCEPTION 'Daily energy refill limit reached (max 3 per day)';
    END IF;

    v_costs := public.get_game_config('energy_refill_costs');
    v_idx := v_count;
    v_cost := COALESCE((v_costs ->> (v_idx - 1))::BIGINT, (v_costs ->> -1)::BIGINT, 600);
    v_refill_amt := public.get_game_config_int('energy_refill_amount', 50)::INTEGER;

    RETURN public.apply_club_economy(
        p_club_id,
        -v_cost,
        v_refill_amt,
        'energy_refill',
        'energy_refill:' || p_club_id::TEXT || ':' || CURRENT_DATE::TEXT || ':' || v_count::TEXT,
        jsonb_build_object('refill_number', v_count, 'cost', v_cost, 'amount', v_refill_amt)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- process_stat_drill — config-driven tiers
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

    SELECT coins, action_energy, daily_drill_count
    INTO v_coins, v_energy, v_daily
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    PERFORM public.assert_not_in_match(p_owner_id);

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
    SET daily_drill_count = daily_drill_count + 1
    WHERE discord_id = p_owner_id;

    v_xp_result := public.apply_card_xp(p_card_id, v_xp_gain, 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'xp_gained', v_xp_gain,
        'levels_gained', COALESCE((v_xp_result->>'levels_gained')::INTEGER, 0),
        'skill_points_granted', COALESCE((v_xp_result->>'skill_points_granted')::INTEGER, 0),
        'new_level', COALESCE((v_xp_result->>'new_level')::INTEGER, 1),
        'coins_spent', v_cost,
        'energy_spent', v_drill_energy,
        'economy', v_econ
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- train_with_fodder — fusion coin sink
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
-- start_player_evolution — config-driven costs
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.start_player_evolution(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_track_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_active CONSTANT INTEGER := 3;
    v_cooldown_hours CONSTANT INTEGER := 10;
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

-- ---------------------------------------------------------------------------
-- process_agent_sale — daily cap
-- ---------------------------------------------------------------------------

DROP FUNCTION IF EXISTS public.process_agent_sale(BIGINT, UUID, BIGINT);

CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ovr INTEGER;
    v_rarity TEXT;
    v_sale_value BIGINT;
    v_sale_count INTEGER;
    v_cap INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);

    v_cap := public.get_game_config_int('agent_sale_daily_cap', 10)::INTEGER;

    INSERT INTO public.agent_sale_daily_log (club_id, sale_date, count)
    VALUES (p_club_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, sale_date)
    DO UPDATE SET count = agent_sale_daily_log.count + 1
    RETURNING count INTO v_sale_count;

    IF v_sale_count > v_cap THEN
        RAISE EXCEPTION 'Daily agent sale limit reached (max % per day)', v_cap;
    END IF;

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

    PERFORM public.apply_club_economy(
        p_club_id,
        v_sale_value,
        0,
        'agent_sale',
        'agent_sale:' || p_card_id::TEXT,
        jsonb_build_object('card_id', p_card_id, 'ovr', v_ovr, 'rarity', v_rarity)
    );

    RETURN v_sale_value;
END;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

GRANT ALL PRIVILEGES ON TABLE public.game_config TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.agent_sale_daily_log TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.energy_refill_daily_log TO anon, authenticated, service_role;

GRANT ALL PRIVILEGES ON FUNCTION public.get_game_config(TEXT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.get_game_config_int(TEXT, BIGINT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.get_game_config_numeric(TEXT, NUMERIC) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.economy_v2_enabled() TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.league_division_tier(TEXT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.league_match_coins(TEXT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.sync_action_energy(BIGINT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.apply_club_economy(BIGINT, BIGINT, INTEGER, TEXT, TEXT, JSONB) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_daily_login(BIGINT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.purchase_energy_refill(BIGINT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale(BIGINT, UUID) TO anon, authenticated, service_role;

-- ponytail: v2 uses lazy sync_action_energy (1/6 min); legacy scheduler tick is a no-op.
CREATE OR REPLACE FUNCTION public.regen_energy_tick() RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    NULL;
END;
$$;

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
      ('table:public.game_config'),
      ('table:public.agent_sale_daily_log'),
      ('table:public.energy_refill_daily_log'),
      ('column:public.players.action_energy'),
      ('column:public.players.last_daily_login'),
      ('column:public.economy_ledger.idempotency_key'),
      ('function:apply_club_economy'),
      ('function:sync_action_energy'),
      ('function:claim_daily_login'),
      ('function:purchase_energy_refill'),
      ('function:get_game_config')
  ) AS req(obj)
  WHERE NOT (
    (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
    OR (
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
        WHEN 'apply_club_economy' THEN to_regprocedure('public.apply_club_economy(bigint,bigint,integer,text,text,jsonb)')
        WHEN 'sync_action_energy' THEN to_regprocedure('public.sync_action_energy(bigint)')
        WHEN 'claim_daily_login' THEN to_regprocedure('public.claim_daily_login(bigint)')
        WHEN 'purchase_energy_refill' THEN to_regprocedure('public.purchase_energy_refill(bigint)')
        WHEN 'get_game_config' THEN to_regprocedure('public.get_game_config(text)')
        ELSE NULL
      END IS NOT NULL
    )
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
  END IF;
END $$;

-- US-38: Audit hardening follow-up — match XP cap lock ordering, economy idempotency replay,
-- evolution POT projection at start/claim.

-- ---------------------------------------------------------------------------
-- Shared OVR computation (read-only; used by recalculate + evolution projection)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.compute_card_ovr(
    p_position TEXT,
    p_pac INTEGER,
    p_sho INTEGER,
    p_pas INTEGER,
    p_dri INTEGER,
    p_def INTEGER,
    p_phy INTEGER,
    p_potential INTEGER,
    p_card_id UUID DEFAULT NULL
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_wpac NUMERIC := 0.10;
    v_wsho NUMERIC := 0.15;
    v_wpas NUMERIC := 0.25;
    v_wdri NUMERIC := 0.20;
    v_wdef NUMERIC := 0.15;
    v_wphy NUMERIC := 0.15;
    v_bonus INTEGER := 0;
    v_base NUMERIC;
    v_ps TEXT;
BEGIN
    IF p_position = 'FWD' THEN
        v_wpac := 0.20; v_wsho := 0.35; v_wpas := 0.10; v_wdri := 0.20; v_wdef := 0.05; v_wphy := 0.10;
    ELSIF p_position = 'DEF' THEN
        v_wpac := 0.15; v_wsho := 0.05; v_wpas := 0.10; v_wdri := 0.05; v_wdef := 0.40; v_wphy := 0.25;
    ELSIF p_position = 'GK' THEN
        v_wpac := 0.15; v_wsho := 0.00; v_wpas := 0.15; v_wdri := 0.00; v_wdef := 0.50; v_wphy := 0.20;
    END IF;

    IF p_card_id IS NOT NULL THEN
        FOR v_ps IN
            SELECT playstyle_key FROM public.player_playstyles WHERE card_id = p_card_id
        LOOP
            IF (v_ps = 'Power Header' AND p_position IN ('FWD', 'DEF'))
                OR (v_ps = 'Playmaker' AND p_position = 'MID')
                OR (v_ps = 'Speedster' AND p_position IN ('FWD', 'MID', 'DEF')) THEN
                v_bonus := v_bonus + 1;
            END IF;
        END LOOP;
    END IF;
    v_bonus := LEAST(v_bonus, 2);

    v_base := (
        p_pac * v_wpac + p_sho * v_wsho + p_pas * v_wpas +
        p_dri * v_wdri + p_def * v_wdef + p_phy * v_wphy
    );

    RETURN LEAST(floor(v_base + v_bonus)::INTEGER, p_potential);
END;
$$;

CREATE OR REPLACE FUNCTION public.recalculate_card_ovr(p_card_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_pos TEXT;
    v_pac INTEGER;
    v_sho INTEGER;
    v_pas INTEGER;
    v_dri INTEGER;
    v_def INTEGER;
    v_phy INTEGER;
    v_potential INTEGER;
    v_ovr INTEGER;
BEGIN
    SELECT position, pac, sho, pas, dri, def, phy, potential
    INTO v_pos, v_pac, v_sho, v_pas, v_dri, v_def, v_phy, v_potential
    FROM public.player_cards
    WHERE id = p_card_id;

    IF v_pos IS NULL THEN
        RAISE EXCEPTION 'Card not found';
    END IF;

    v_ovr := public.compute_card_ovr(
        v_pos, v_pac, v_sho, v_pas, v_dri, v_def, v_phy, v_potential, p_card_id
    );

    UPDATE public.player_cards SET overall = v_ovr WHERE id = p_card_id;
    RETURN v_ovr;
END;
$$;

CREATE OR REPLACE FUNCTION public.peek_card_ovr(
    p_card_id UUID,
    p_stat_col TEXT,
    p_stat_val INTEGER
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_pos TEXT;
    v_pac INTEGER;
    v_sho INTEGER;
    v_pas INTEGER;
    v_dri INTEGER;
    v_def INTEGER;
    v_phy INTEGER;
    v_potential INTEGER;
BEGIN
    SELECT position, pac, sho, pas, dri, def, phy, potential
    INTO v_pos, v_pac, v_sho, v_pas, v_dri, v_def, v_phy, v_potential
    FROM public.player_cards
    WHERE id = p_card_id;

    IF v_pos IS NULL THEN
        RETURN 0;
    END IF;

    IF p_stat_col = 'pac' THEN v_pac := p_stat_val;
    ELSIF p_stat_col = 'sho' THEN v_sho := p_stat_val;
    ELSIF p_stat_col = 'pas' THEN v_pas := p_stat_val;
    ELSIF p_stat_col = 'dri' THEN v_dri := p_stat_val;
    ELSIF p_stat_col = 'def' THEN v_def := p_stat_val;
    ELSIF p_stat_col = 'phy' THEN v_phy := p_stat_val;
    ELSE
        RAISE EXCEPTION 'Invalid stat column';
    END IF;

    RETURN public.compute_card_ovr(
        v_pos, v_pac, v_sho, v_pas, v_dri, v_def, v_phy, v_potential, p_card_id
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.evolution_stat_reward_steps(
    p_card_id UUID,
    p_stat_col TEXT,
    p_max_steps INTEGER DEFAULT 5
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_current INTEGER;
    v_overall INTEGER;
    v_potential INTEGER;
    v_steps INTEGER := 0;
    v_trial INTEGER;
    v_trial_ovr INTEGER;
BEGIN
    EXECUTE format(
        'SELECT %I, overall, potential FROM public.player_cards WHERE id = $1',
        p_stat_col
    ) INTO v_current, v_overall, v_potential USING p_card_id;

    IF v_current IS NULL THEN
        RETURN 0;
    END IF;
    IF v_overall >= v_potential OR v_current >= 99 THEN
        RETURN 0;
    END IF;

    FOR i IN 1..GREATEST(0, p_max_steps) LOOP
        EXIT WHEN v_current + v_steps >= 99;
        v_trial := v_current + v_steps + 1;
        v_trial_ovr := public.peek_card_ovr(p_card_id, p_stat_col, v_trial);
        IF v_trial_ovr > v_potential THEN
            EXIT;
        END IF;
        v_steps := v_steps + 1;
    END LOOP;

    RETURN v_steps;
END;
$$;

-- ---------------------------------------------------------------------------
-- apply_card_xp: lock card before match daily cap read (race hardening)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.apply_card_xp(
    p_card_id UUID,
    p_xp_amount INTEGER,
    p_source TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_xp INTEGER;
    v_old_level INTEGER;
    v_new_xp INTEGER;
    v_new_level INTEGER;
    v_levels_gained INTEGER;
    v_points INTEGER;
    v_cap_xp INTEGER;
    v_xp_added INTEGER;
    v_xp_wasted INTEGER;
    v_effective_xp INTEGER;
    v_match_used INTEGER;
    v_match_allowance INTEGER;
    v_points_per_level CONSTANT INTEGER := 3;
    v_l_max CONSTANT INTEGER := 100;
    v_match_daily_cap CONSTANT INTEGER := 100;
BEGIN
    v_effective_xp := COALESCE(p_xp_amount, 0);

    SELECT xp INTO v_xp
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    IF v_xp IS NULL THEN
        RAISE EXCEPTION 'Card not found';
    END IF;

    IF p_source = 'match_simulation' AND v_effective_xp > 0 THEN
        v_match_used := public.daily_match_xp_used(p_card_id);
        v_match_allowance := GREATEST(0, v_match_daily_cap - v_match_used);
        v_effective_xp := LEAST(v_effective_xp, v_match_allowance);
    END IF;

    v_old_level := public.level_from_xp(v_xp);

    IF v_old_level >= v_l_max OR v_effective_xp <= 0 THEN
        RETURN jsonb_build_object(
            'old_level', v_old_level,
            'new_level', v_old_level,
            'levels_gained', 0,
            'skill_points_granted', 0,
            'xp_added', 0,
            'xp_wasted', CASE
                WHEN v_old_level >= v_l_max AND COALESCE(p_xp_amount, 0) > 0 THEN p_xp_amount
                ELSE 0
            END,
            'new_xp', v_xp
        );
    END IF;

    v_cap_xp := public.cumulative_xp_for_level(v_l_max);
    v_new_xp := LEAST(v_xp + v_effective_xp, v_cap_xp);
    v_xp_added := v_new_xp - v_xp;
    v_xp_wasted := GREATEST(0, v_xp + v_effective_xp - v_cap_xp)
        + GREATEST(0, COALESCE(p_xp_amount, 0) - v_effective_xp);
    v_new_level := public.level_from_xp(v_new_xp);
    v_levels_gained := v_new_level - v_old_level;
    v_points := v_levels_gained * v_points_per_level;

    UPDATE public.player_cards
    SET
        xp = v_new_xp,
        level = v_new_level,
        skill_points = skill_points + v_points,
        skill_points_earned = skill_points_earned + v_points,
        last_level_up_at = CASE WHEN v_levels_gained > 0 THEN NOW() ELSE last_level_up_at END
    WHERE id = p_card_id;

    IF v_xp_added > 0 THEN
        INSERT INTO public.player_xp_log (card_id, xp_amount, source)
        VALUES (p_card_id, v_xp_added, p_source);
    END IF;

    RETURN jsonb_build_object(
        'old_level', v_old_level,
        'new_level', v_new_level,
        'levels_gained', v_levels_gained,
        'skill_points_granted', v_points,
        'xp_added', v_xp_added,
        'xp_wasted', v_xp_wasted,
        'new_xp', v_new_xp
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- apply_club_economy: graceful replay on concurrent idempotency-key insert
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
        BEGIN
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
        EXCEPTION
            WHEN unique_violation THEN
                IF p_idempotency_key IS NULL THEN
                    RAISE;
                END IF;
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
                RAISE;
        END;
    ELSIF p_idempotency_key IS NOT NULL THEN
        BEGIN
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
        EXCEPTION
            WHEN unique_violation THEN
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
                RAISE;
        END;
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
-- Evolution: POT projection at start; incremental clamp at claim
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.claim_evolution_reward(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card_id UUID;
    v_evo_id TEXT;
    v_progress INTEGER;
    v_goal INTEGER;
    v_stat_col TEXT;
    v_reward_max INTEGER := 5;
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

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1',
        v_stat_col
    ) INTO v_current USING v_card_id;

    v_applied := public.evolution_stat_reward_steps(v_card_id, v_stat_col, v_reward_max);
    v_new_val := v_current;
    IF v_applied > 0 THEN
        v_new_val := v_current + v_applied;
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
        'reward_max', v_reward_max,
        'reward_clamped', (v_applied > 0 AND v_applied < v_reward_max),
        'blocked_by_cap', (v_applied = 0 AND v_overall >= v_potential AND v_current < 99)
    );
END;
$$;

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
    v_stat_col TEXT;
    v_reward_steps INTEGER;
    v_current INTEGER;
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

    v_stat_col := CASE p_track_id
        WHEN 'pace_boost' THEN 'pac'
        WHEN 'shooting_star' THEN 'sho'
        WHEN 'def_wall' THEN 'def'
        ELSE 'pac'
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

    SELECT id, owner_id, overall, level, potential INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF v_card.id IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;

    IF v_card.level < v_min_level THEN
        RAISE EXCEPTION 'Player level too low for this evolution (requires level %)', v_min_level;
    END IF;

    IF v_card.overall >= v_card.potential THEN
        RAISE EXCEPTION 'Player is already at maximum overall for their potential';
    END IF;

    v_reward_steps := public.evolution_stat_reward_steps(p_card_id, v_stat_col, 5);
    IF v_reward_steps <= 0 THEN
        RAISE EXCEPTION 'Evolution reward would exceed this player''s potential';
    END IF;

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1',
        v_stat_col
    ) INTO v_current USING p_card_id;

    IF public.peek_card_ovr(p_card_id, v_stat_col, v_current + v_reward_steps) > v_card.potential THEN
        RAISE EXCEPTION 'Evolution reward would exceed this player''s potential';
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
        'reward_steps_projected', v_reward_steps,
        'economy', v_econ
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.compute_card_ovr TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.peek_card_ovr TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.evolution_stat_reward_steps TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.apply_card_xp TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.apply_club_economy TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_evolution_reward TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.start_player_evolution TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.recalculate_card_ovr TO anon, authenticated, service_role;

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
            ('function:compute_card_ovr'),
            ('function:peek_card_ovr'),
            ('function:evolution_stat_reward_steps'),
            ('function:apply_card_xp'),
            ('function:apply_club_economy'),
            ('function:claim_evolution_reward'),
            ('function:start_player_evolution')
    ) AS req(obj)
    WHERE NOT (
        req.obj LIKE 'function:%'
        AND CASE split_part(req.obj, ':', 2)
            WHEN 'compute_card_ovr' THEN to_regprocedure('public.compute_card_ovr(text,integer,integer,integer,integer,integer,integer,integer,uuid)')
            WHEN 'peek_card_ovr' THEN to_regprocedure('public.peek_card_ovr(uuid,text,integer)')
            WHEN 'evolution_stat_reward_steps' THEN to_regprocedure('public.evolution_stat_reward_steps(uuid,text,integer)')
            WHEN 'apply_card_xp' THEN to_regprocedure('public.apply_card_xp(uuid,integer,text)')
            WHEN 'apply_club_economy' THEN to_regprocedure('public.apply_club_economy(bigint,bigint,integer,text,text,jsonb)')
            WHEN 'claim_evolution_reward' THEN to_regprocedure('public.claim_evolution_reward(bigint,uuid)')
            WHEN 'start_player_evolution' THEN to_regprocedure('public.start_player_evolution(bigint,uuid,text)')
            ELSE NULL
        END IS NOT NULL
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 038 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

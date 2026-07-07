-- US-23: Dynamic player leveling — XP pipeline, skill points, retroactive catch-up.

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------

ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS skill_points_earned INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS skill_points_spent  INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_level_up_at   TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS public.pending_level_rewards (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id        BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    player_id      UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    missing_points INTEGER NOT NULL CHECK (missing_points > 0),
    claimed        BOOLEAN NOT NULL DEFAULT FALSE,
    notified       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at     TIMESTAMPTZ,
    UNIQUE (player_id)
);

CREATE TABLE IF NOT EXISTS public.fusion_daily_log (
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    fusion_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (club_id, fusion_date)
);

GRANT ALL PRIVILEGES ON TABLE public.pending_level_rewards TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.fusion_daily_log TO anon, authenticated, service_role;

-- Backfill earned from legacy available balance
UPDATE public.player_cards
SET skill_points_earned = skill_points
WHERE skill_points_earned = 0 AND skill_points > 0;

-- ---------------------------------------------------------------------------
-- XP curve helpers (mirror packages/player_engine/progression.py)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.xp_needed_for_level(p_level INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_level < 1 OR p_level >= 100 THEN
        RETURN 0;
    END IF;
    RETURN floor(100.0 * power(1.12, p_level - 1))::INTEGER;
END;
$$;

CREATE OR REPLACE FUNCTION public.cumulative_xp_for_level(p_level INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_i INTEGER;
    v_acc INTEGER := 0;
BEGIN
    IF p_level <= 1 THEN
        RETURN 0;
    END IF;
    FOR v_i IN 1..LEAST(p_level - 1, 99) LOOP
        v_acc := v_acc + public.xp_needed_for_level(v_i);
    END LOOP;
    RETURN v_acc;
END;
$$;

CREATE OR REPLACE FUNCTION public.level_from_xp(p_xp INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_lvl INTEGER := 1;
    v_acc INTEGER := 0;
    v_needed INTEGER;
BEGIN
    IF p_xp IS NULL OR p_xp <= 0 THEN
        RETURN 1;
    END IF;
    WHILE v_lvl < 100 LOOP
        v_needed := public.xp_needed_for_level(v_lvl);
        IF v_needed <= 0 OR p_xp < v_acc + v_needed THEN
            EXIT;
        END IF;
        v_acc := v_acc + v_needed;
        v_lvl := v_lvl + 1;
    END LOOP;
    RETURN v_lvl;
END;
$$;

-- ---------------------------------------------------------------------------
-- Core XP pipeline
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
    v_points_per_level CONSTANT INTEGER := 3;
    v_l_max CONSTANT INTEGER := 100;
BEGIN
    SELECT xp INTO v_xp
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    IF v_xp IS NULL THEN
        RAISE EXCEPTION 'Card not found';
    END IF;

    v_old_level := public.level_from_xp(v_xp);

    IF v_old_level >= v_l_max OR COALESCE(p_xp_amount, 0) <= 0 THEN
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
    v_new_xp := LEAST(v_xp + p_xp_amount, v_cap_xp);
    v_xp_added := v_new_xp - v_xp;
    v_xp_wasted := GREATEST(0, v_xp + p_xp_amount - v_cap_xp);
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
-- Retroactive catch-up
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.claim_pending_level_rewards(p_owner_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_row RECORD;
    v_total INTEGER := 0;
    v_count INTEGER := 0;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    FOR v_row IN
        SELECT pr.player_id, pr.missing_points
        FROM public.pending_level_rewards pr
        JOIN public.player_cards c ON c.id = pr.player_id
        WHERE pr.club_id = p_owner_id
          AND NOT pr.claimed
          AND c.owner_id = p_owner_id
        FOR UPDATE OF pr
    LOOP
        UPDATE public.player_cards
        SET
            skill_points = skill_points + v_row.missing_points,
            skill_points_earned = skill_points_earned + v_row.missing_points
        WHERE id = v_row.player_id AND owner_id = p_owner_id;

        UPDATE public.pending_level_rewards
        SET claimed = TRUE, claimed_at = NOW()
        WHERE player_id = v_row.player_id AND NOT claimed;

        v_total := v_total + v_row.missing_points;
        v_count := v_count + 1;
    END LOOP;

    RETURN jsonb_build_object('players_claimed', v_count, 'total_points', v_total);
END;
$$;

-- Sync level from XP and seed pending rewards for legacy players
UPDATE public.player_cards
SET level = public.level_from_xp(COALESCE(xp, 0));

INSERT INTO public.pending_level_rewards (club_id, player_id, missing_points)
SELECT
    c.owner_id,
    c.id,
    (public.level_from_xp(COALESCE(c.xp, 0)) - 1) * 3 - COALESCE(c.skill_points_earned, 0)
FROM public.player_cards c
WHERE (public.level_from_xp(COALESCE(c.xp, 0)) - 1) * 3 > COALESCE(c.skill_points_earned, 0)
ON CONFLICT (player_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Match XP → apply_card_xp
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.process_match_result(
    p_result TEXT,
    p_card_ids UUID[],
    p_xp_amount INTEGER,
    p_card_ratings NUMERIC[] DEFAULT NULL
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_card_id UUID;
    v_morale_delta INTEGER;
    v_i INTEGER;
    v_rating NUMERIC;
    v_recent JSONB;
    v_age INTEGER;
    v_pot INTEGER;
    v_init_pot INTEGER;
    v_high INTEGER;
    v_boost INTEGER;
    v_new_pot INTEGER;
BEGIN
    IF p_result = 'win' THEN
        v_morale_delta := 5;
    ELSIF p_result = 'draw' THEN
        v_morale_delta := 1;
    ELSE
        v_morale_delta := -5;
    END IF;

    FOR v_i IN 1..COALESCE(array_length(p_card_ids, 1), 0) LOOP
        v_card_id := p_card_ids[v_i];

        IF p_card_ratings IS NOT NULL AND array_length(p_card_ratings, 1) >= v_i THEN
            v_rating := p_card_ratings[v_i];
        ELSE
            v_rating := NULL;
        END IF;

        SELECT age, potential, initial_potential, recent_match_ratings
        INTO v_age, v_pot, v_init_pot, v_recent
        FROM public.player_cards
        WHERE id = v_card_id
        FOR UPDATE;

        IF v_rating IS NOT NULL THEN
            v_recent := COALESCE(v_recent, '[]'::jsonb) || to_jsonb(v_rating);
            IF jsonb_array_length(v_recent) > 5 THEN
                v_recent := (
                    SELECT COALESCE(jsonb_agg(val ORDER BY ord), '[]'::jsonb)
                    FROM (
                        SELECT value AS val, ord
                        FROM jsonb_array_elements(v_recent) WITH ORDINALITY AS t(value, ord)
                        ORDER BY ord DESC
                        LIMIT 5
                    ) sub
                );
            END IF;

            v_init_pot := COALESCE(v_init_pot, v_pot);
            v_boost := 0;

            IF v_age BETWEEN 16 AND 21 AND jsonb_array_length(v_recent) >= 3 THEN
                SELECT COUNT(*)::INTEGER INTO v_high
                FROM jsonb_array_elements(v_recent) elem
                WHERE (elem #>> '{}')::NUMERIC >= 8.0;

                IF v_high >= 3 AND random() < 0.20 THEN
                    v_boost := 2 + floor(random() * 4)::INTEGER;
                    v_new_pot := LEAST(99, LEAST(v_pot + v_boost, v_init_pot + 10));
                    IF v_new_pot > v_pot THEN
                        v_pot := v_new_pot;
                    END IF;
                END IF;
            END IF;

            UPDATE public.player_cards
            SET
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta)),
                recent_match_ratings = v_recent,
                potential = v_pot
            WHERE id = v_card_id;
        ELSE
            UPDATE public.player_cards
            SET morale = LEAST(100, GREATEST(10, morale + v_morale_delta))
            WHERE id = v_card_id;
        END IF;

        PERFORM public.apply_card_xp(v_card_id, p_xp_amount, 'match_simulation');
    END LOOP;

    PERFORM public.tick_evolution_match_progress(p_card_ids);
    RETURN TRUE;
END;
$$;

-- ---------------------------------------------------------------------------
-- Stat drills → XP only
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
    v_drill_energy INTEGER := 15;
    v_drill_coin_mult INTEGER := 5;
    v_drill_min_level INTEGER := 1;
    v_drill_xp_base INTEGER := 25;
    v_xp_gain INTEGER;
    v_xp_result JSONB;
BEGIN
    PERFORM public.sync_training_energy(p_owner_id);

    SELECT training_energy, coins, daily_drill_count
    INTO v_energy, v_coins, v_daily
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

    IF v_card_level < v_drill_min_level THEN
        RAISE EXCEPTION 'Player level too low for this drill (requires level %)', v_drill_min_level;
    END IF;

    IF v_energy < v_drill_energy THEN
        RAISE EXCEPTION 'Insufficient training energy';
    END IF;

    v_cost := (v_drill_coin_mult * v_ovr)::BIGINT;
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

    UPDATE public.players
    SET
        training_energy = training_energy - v_drill_energy,
        coins = coins - v_cost,
        daily_drill_count = daily_drill_count + 1
    WHERE discord_id = p_owner_id;

    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_owner_id, -v_cost, 'coins', 'stat_drill_' || p_drill_id);

    v_xp_result := public.apply_card_xp(p_card_id, v_xp_gain, 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'drill_id', p_drill_id,
        'xp_gained', v_xp_gain,
        'levels_gained', COALESCE((v_xp_result->>'levels_gained')::INTEGER, 0),
        'skill_points_granted', COALESCE((v_xp_result->>'skill_points_granted')::INTEGER, 0),
        'new_ovr', v_ovr,
        'coins_spent', v_cost,
        'stat', NULL,
        'new_level', COALESCE((v_xp_result->>'new_level')::INTEGER, v_card_level)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Card fusion → XP via apply_card_xp
-- ---------------------------------------------------------------------------

DROP FUNCTION IF EXISTS public.train_with_fodder(BIGINT, UUID, UUID);

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
    v_xp_result JSONB;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

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

    v_fusion_xp := 50
        + (GREATEST(1, v_fodder_level) * 8)
        + (GREATEST(0, v_fodder_overall) * 2);

    DELETE FROM public.player_cards WHERE id = p_fodder_id;

    v_xp_result := public.apply_card_xp(p_target_id, v_fusion_xp, 'fusion');

    RETURN jsonb_build_object(
        'fusion_xp', v_fusion_xp,
        'levels_gained', COALESCE((v_xp_result->>'levels_gained')::INTEGER, 0),
        'skill_points_granted', COALESCE((v_xp_result->>'skill_points_granted')::INTEGER, 0),
        'new_level', COALESCE((v_xp_result->>'new_level')::INTEGER, 1),
        'new_ovr', v_target_overall,
        'xp_wasted', COALESCE((v_xp_result->>'xp_wasted')::INTEGER, 0)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Skill allocation with POT cap + spent tracking
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.allocate_skill_point(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_stat TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_col TEXT;
    v_points INTEGER;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_overall INTEGER;
    v_potential INTEGER;
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
        'SELECT skill_points, overall, potential, %I FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',
        v_col
    ) INTO v_points, v_overall, v_potential, v_current USING p_card_id, p_owner_id;

    IF v_points IS NULL THEN
        RAISE EXCEPTION 'Card not found or not owned';
    END IF;
    IF v_points <= 0 THEN
        RAISE EXCEPTION 'No skill points available';
    END IF;
    IF v_current >= 99 THEN
        RAISE EXCEPTION 'Stat already at maximum';
    END IF;
    IF v_overall >= v_potential THEN
        RAISE EXCEPTION 'Player is already at maximum overall for their potential';
    END IF;

    v_new_val := v_current + 1;
    EXECUTE format(
        'UPDATE public.player_cards SET %I = $1, skill_points = skill_points - 1, skill_points_spent = skill_points_spent + 1 WHERE id = $2',
        v_col
    ) USING v_new_val, p_card_id;

    v_new_ovr := public.recalculate_card_ovr(p_card_id);

    IF v_new_ovr > v_potential THEN
        RAISE EXCEPTION 'Would exceed maximum overall for their potential';
    END IF;

    RETURN jsonb_build_object('new_ovr', v_new_ovr, 'stat', upper(v_col), 'new_value', v_new_val);
END;
$$;

-- ---------------------------------------------------------------------------
-- Evolution start: min player level gate
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
    v_min_level INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.sync_training_energy(p_owner_id);

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
        'goal', v_goal,
        'active_count', v_active_count + 1,
        'cooldown_ends_at', v_cooldown_ends,
        'is_replacement', v_is_replacement
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.xp_needed_for_level(integer) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.cumulative_xp_for_level(integer) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.level_from_xp(integer) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.apply_card_xp(uuid, integer, text) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_pending_level_rewards(bigint) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_match_result(text, uuid[], integer, numeric[]) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill(bigint, uuid, text) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.train_with_fodder(bigint, uuid, uuid) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.allocate_skill_point(bigint, uuid, text) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.start_player_evolution(bigint, uuid, text) TO anon, authenticated, service_role;

-- ponytail: O(n) schema audit; extend REQUIRED_* arrays when adding tables/columns.
DO $$
DECLARE
    v_missing TEXT[];
BEGIN
  SELECT array_agg(req.obj ORDER BY req.obj)
  INTO v_missing
  FROM (
    VALUES
      ('table:public.pending_level_rewards'),
      ('table:public.fusion_daily_log'),
      ('column:public.player_cards.skill_points_earned'),
      ('column:public.player_cards.skill_points_spent'),
      ('column:public.player_cards.last_level_up_at'),
      ('function:apply_card_xp'),
      ('function:claim_pending_level_rewards'),
      ('function:level_from_xp')
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
        WHEN 'apply_card_xp' THEN to_regprocedure('public.apply_card_xp(uuid,integer,text)')
        WHEN 'claim_pending_level_rewards' THEN to_regprocedure('public.claim_pending_level_rewards(bigint)')
        WHEN 'level_from_xp' THEN to_regprocedure('public.level_from_xp(integer)')
        ELSE NULL
      END IS NOT NULL
    )
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
  END IF;
END $$;

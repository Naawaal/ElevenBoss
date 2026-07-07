-- US-24: Progression hardening — claim ownership, retro scale, daily caps

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------

ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS daily_alloc_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS alloc_reset_date DATE;

CREATE TABLE IF NOT EXISTS public.player_drill_daily_log (
    card_id    UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    drill_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (card_id, drill_date)
);

GRANT ALL PRIVILEGES ON TABLE public.player_drill_daily_log TO anon, authenticated, service_role;

-- Sync owner + scale unclaimed retro rewards (75%, cap 18)
UPDATE public.pending_level_rewards pr
SET
    club_id = c.owner_id,
    missing_points = LEAST(
        18,
        GREATEST(1, (pr.missing_points * 75) / 100)
    )
FROM public.player_cards c
WHERE c.id = pr.player_id
  AND NOT pr.claimed;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.daily_match_xp_used(p_card_id UUID)
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(SUM(xp_amount), 0)::INTEGER
    FROM public.player_xp_log
    WHERE card_id = p_card_id
      AND source = 'match_simulation'
      AND created_at >= CURRENT_DATE;
$$;

CREATE OR REPLACE FUNCTION public.count_unclaimed_level_rewards(p_owner_id BIGINT)
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(*)::INTEGER
    FROM public.pending_level_rewards pr
    JOIN public.player_cards c ON c.id = pr.player_id
    WHERE NOT pr.claimed
      AND c.owner_id = p_owner_id;
$$;

-- ---------------------------------------------------------------------------
-- apply_card_xp — match XP daily cap (100/card/day)
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

    IF p_source = 'match_simulation' AND v_effective_xp > 0 THEN
        v_match_used := public.daily_match_xp_used(p_card_id);
        v_match_allowance := GREATEST(0, v_match_daily_cap - v_match_used);
        v_effective_xp := LEAST(v_effective_xp, v_match_allowance);
    END IF;

    SELECT xp INTO v_xp
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    IF v_xp IS NULL THEN
        RAISE EXCEPTION 'Card not found';
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
-- claim_pending_level_rewards — current owner only
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
        WHERE NOT pr.claimed
          AND c.owner_id = p_owner_id
        FOR UPDATE OF pr
    LOOP
        UPDATE public.player_cards
        SET
            skill_points = skill_points + v_row.missing_points,
            skill_points_earned = skill_points_earned + v_row.missing_points
        WHERE id = v_row.player_id AND owner_id = p_owner_id;

        UPDATE public.pending_level_rewards
        SET
            claimed = TRUE,
            claimed_at = NOW(),
            club_id = p_owner_id
        WHERE player_id = v_row.player_id AND NOT claimed;

        v_total := v_total + v_row.missing_points;
        v_count := v_count + 1;
    END LOOP;

    RETURN jsonb_build_object('players_claimed', v_count, 'total_points', v_total);
END;
$$;

-- ---------------------------------------------------------------------------
-- allocate_skill_point — pacing + SAVEPOINT POT check
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
    v_alloc_count INTEGER;
    v_alloc_reset DATE;
    v_alloc_cap CONSTANT INTEGER := 15;
    v_pacing_until CONSTANT DATE := DATE '2026-08-06';
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
        'SELECT skill_points, overall, potential, %I, daily_alloc_count, alloc_reset_date '
        || 'FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',
        v_col
    ) INTO v_points, v_overall, v_potential, v_current, v_alloc_count, v_alloc_reset
    USING p_card_id, p_owner_id;

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

    IF CURRENT_DATE <= v_pacing_until THEN
        IF v_alloc_reset IS NULL OR v_alloc_reset < CURRENT_DATE THEN
            v_alloc_count := 0;
            UPDATE public.player_cards
            SET daily_alloc_count = 0, alloc_reset_date = CURRENT_DATE
            WHERE id = p_card_id;
        END IF;
        IF v_alloc_count >= v_alloc_cap THEN
            RAISE EXCEPTION 'Daily skill allocation limit reached for this player (max % per day during pacing period)', v_alloc_cap;
        END IF;
    END IF;

    v_new_val := v_current + 1;

    EXECUTE format(
        'UPDATE public.player_cards SET %I = $1, skill_points = skill_points - 1, '
        || 'skill_points_spent = skill_points_spent + 1, daily_alloc_count = daily_alloc_count + 1, '
        || 'alloc_reset_date = CURRENT_DATE WHERE id = $2',
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
-- process_stat_drill — per-player daily cap (5)
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
    v_player_drill_count INTEGER;
    v_player_drill_cap CONSTANT INTEGER := 5;
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

    INSERT INTO public.player_drill_daily_log (card_id, drill_date, count)
    VALUES (p_card_id, CURRENT_DATE, 1)
    ON CONFLICT (card_id, drill_date)
    DO UPDATE SET count = player_drill_daily_log.count + 1
    RETURNING count INTO v_player_drill_count;

    IF v_player_drill_count > v_player_drill_cap THEN
        RAISE EXCEPTION 'Daily drill limit reached for this player (max % per day)', v_player_drill_cap;
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
        'xp_gained', v_xp_gain,
        'levels_gained', COALESCE((v_xp_result->>'levels_gained')::INTEGER, 0),
        'skill_points_granted', COALESCE((v_xp_result->>'skill_points_granted')::INTEGER, 0),
        'new_level', COALESCE((v_xp_result->>'new_level')::INTEGER, 1)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

GRANT ALL PRIVILEGES ON FUNCTION public.daily_match_xp_used(uuid) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.count_unclaimed_level_rewards(bigint) TO anon, authenticated, service_role;

-- ponytail: extend guard lists when adding progression hardening objects.
DO $$
DECLARE
    v_missing TEXT[];
BEGIN
  SELECT array_agg(req.obj ORDER BY req.obj)
  INTO v_missing
  FROM (
    VALUES
      ('table:public.player_drill_daily_log'),
      ('column:public.player_cards.daily_alloc_count'),
      ('column:public.player_cards.alloc_reset_date'),
      ('function:count_unclaimed_level_rewards'),
      ('function:daily_match_xp_used')
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
        WHEN 'count_unclaimed_level_rewards' THEN to_regprocedure('public.count_unclaimed_level_rewards(bigint)')
        WHEN 'daily_match_xp_used' THEN to_regprocedure('public.daily_match_xp_used(uuid)')
        ELSE NULL
      END IS NOT NULL
    )
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
  END IF;
END $$;

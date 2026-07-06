-- Fix: migration 020 treated daily_drill_limit as a players column; it is a constant (20).
-- Also ensure tables from earlier migrations exist on DBs that skipped them.

CREATE TABLE IF NOT EXISTS public.active_training (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    card_id     UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    drill_type  TEXT NOT NULL CHECK (drill_type IN ('cardio', 'tactics', 'match_prep')),
    end_time    TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT ALL PRIVILEGES ON TABLE public.active_training TO anon, authenticated, service_role;

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

GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill TO anon, authenticated, service_role;

-- ponytail: O(n) schema audit; extend REQUIRED_* arrays when adding tables/columns.
DO $$
DECLARE
    v_missing TEXT[];
BEGIN
  SELECT array_agg(req.obj ORDER BY req.obj)
  INTO v_missing
  FROM (
    VALUES
      ('table:public.active_training'),
      ('table:public.economy_ledger'),
      ('table:public.league_members'),
      ('table:public.match_locks'),
      ('table:public.match_runs'),
      ('column:public.players.training_energy'),
      ('column:public.players.daily_drill_count'),
      ('column:public.players.daily_drill_reset_at')
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
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
  END IF;
END $$;

-- Feature 053 US2: finalize_pvp_match (atomic dual rewards + LP)
-- Forward after 098/099. Flag pvp_rewards_enabled gates economy/LP.

CREATE OR REPLACE FUNCTION public.finalize_pvp_match(
    p_run_id UUID,
    p_home_score INTEGER,
    p_away_score INTEGER,
    p_home_rating NUMERIC DEFAULT 0,
    p_away_rating NUMERIC DEFAULT 0
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_home public.players%ROWTYPE;
    v_away public.players%ROWTYPE;
    v_rewards BOOLEAN;
    v_cost INTEGER;
    v_prov INTEGER;
    v_home_res TEXT;
    v_away_res TEXT;
    v_home_coins INTEGER := 0;
    v_away_coins INTEGER := 0;
    v_home_lp INTEGER := 0;
    v_away_lp INTEGER := 0;
    v_home_win_coins INTEGER;
    v_away_win_coins INTEGER;
    v_mult NUMERIC;
    v_raw_lp INTEGER;
    v_new_lp INTEGER;
    v_hist_home UUID;
    v_hist_away UUID;
    v_prior JSONB;
    v_id1 BIGINT;
    v_id2 BIGINT;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Match run not found';
    END IF;
    IF v_run.run_type <> 'pvp' THEN
        RAISE EXCEPTION 'finalize_pvp_match requires run_type=pvp';
    END IF;

    -- Idempotent: already completed
    IF v_run.status = 'completed' THEN
        SELECT reason_meta INTO v_prior
        FROM public.economy_ledger
        WHERE idempotency_key = 'pvp_finalize:' || p_run_id::TEXT
        LIMIT 1;
        RETURN COALESCE(v_prior, jsonb_build_object(
            'ok', true, 'already', true, 'run_id', p_run_id,
            'home', jsonb_build_object('coins', 0, 'lp_delta', 0),
            'away', jsonb_build_object('coins', 0, 'lp_delta', 0)
        ));
    END IF;

    IF v_run.status NOT IN ('streaming', 'completing') THEN
        RAISE EXCEPTION 'Run not finalizable (status=%)', v_run.status;
    END IF;

    UPDATE public.match_runs SET status = 'completing', updated_at = NOW() WHERE id = p_run_id;

    SELECT * INTO v_home FROM public.players WHERE discord_id = v_run.home_discord_id FOR UPDATE;
    SELECT * INTO v_away FROM public.players WHERE discord_id = v_run.away_discord_id FOR UPDATE;
    IF NOT FOUND OR v_home.discord_id IS NULL OR v_away.discord_id IS NULL THEN
        RAISE EXCEPTION 'PvP managers missing';
    END IF;

    IF p_home_score > p_away_score THEN
        v_home_res := 'win'; v_away_res := 'loss';
    ELSIF p_home_score < p_away_score THEN
        v_home_res := 'loss'; v_away_res := 'win';
    ELSE
        v_home_res := 'draw'; v_away_res := 'draw';
    END IF;

    v_rewards := COALESCE((public.get_game_config('pvp_rewards_enabled') #>> '{}')::BOOLEAN, FALSE)
                 AND public._pvp_flag_on();
    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;
    v_prov := public.get_game_config_int('pvp_provisional_matches', 5)::INTEGER;

    SELECT win_coins INTO v_home_win_coins
    FROM public.global_divisions
    WHERE v_home.global_lp >= min_lp
    ORDER BY min_lp DESC LIMIT 1;
    SELECT win_coins INTO v_away_win_coins
    FROM public.global_divisions
    WHERE v_away.global_lp >= min_lp
    ORDER BY min_lp DESC LIMIT 1;
    v_home_win_coins := COALESCE(v_home_win_coins, 100);
    v_away_win_coins := COALESCE(v_away_win_coins, 100);

    IF v_rewards THEN
        -- Home coins
        v_mult := CASE v_home_res
            WHEN 'win' THEN public.get_game_config_numeric('pvp_coin_multiplier_win', 1.25)
            WHEN 'draw' THEN public.get_game_config_numeric('pvp_coin_multiplier_draw', 1.10)
            ELSE public.get_game_config_numeric('pvp_coin_multiplier_loss', 1.00)
        END;
        v_home_coins := GREATEST(0, FLOOR(
            CASE v_home_res
                WHEN 'win' THEN v_home_win_coins
                WHEN 'draw' THEN v_home_win_coins / 3
                ELSE GREATEST(15, v_home_win_coins / 10)
            END * v_mult
        )::INTEGER);

        v_mult := CASE v_away_res
            WHEN 'win' THEN public.get_game_config_numeric('pvp_coin_multiplier_win', 1.25)
            WHEN 'draw' THEN public.get_game_config_numeric('pvp_coin_multiplier_draw', 1.10)
            ELSE public.get_game_config_numeric('pvp_coin_multiplier_loss', 1.00)
        END;
        v_away_coins := GREATEST(0, FLOOR(
            CASE v_away_res
                WHEN 'win' THEN v_away_win_coins
                WHEN 'draw' THEN v_away_win_coins / 3
                ELSE GREATEST(15, v_away_win_coins / 10)
            END * v_mult
        )::INTEGER);

        PERFORM public.sync_action_energy(v_home.discord_id);
        PERFORM public.sync_action_energy(v_away.discord_id);

        PERFORM public.apply_club_economy(
            v_home.discord_id, v_home_coins, -v_cost,
            'match_pvp_' || v_home_res,
            'match:' || p_run_id::TEXT || ':' || v_home.discord_id::TEXT,
            jsonb_build_object('match_type', 'pvp', 'result', v_home_res, 'run_id', p_run_id)
        );
        PERFORM public.apply_club_economy(
            v_away.discord_id, v_away_coins, -v_cost,
            'match_pvp_' || v_away_res,
            'match:' || p_run_id::TEXT || ':' || v_away.discord_id::TEXT,
            jsonb_build_object('match_type', 'pvp', 'result', v_away_res, 'run_id', p_run_id)
        );

        -- LP with provisional loss protection
        v_raw_lp := CASE v_home_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_home_res = 'loss' AND COALESCE(v_home.pvp_ranked_matches, 0) < v_prov THEN
            v_raw_lp := (v_raw_lp / 2);
        END IF;
        v_new_lp := GREATEST(0, v_home.global_lp + v_raw_lp);
        v_home_lp := v_new_lp - v_home.global_lp;

        v_raw_lp := CASE v_away_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_away_res = 'loss' AND COALESCE(v_away.pvp_ranked_matches, 0) < v_prov THEN
            v_raw_lp := (v_raw_lp / 2);
        END IF;
        v_new_lp := GREATEST(0, v_away.global_lp + v_raw_lp);
        v_away_lp := v_new_lp - v_away.global_lp;

        PERFORM public.increment_match_career_stats(
            v_home.discord_id, v_home_res,
            CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
            v_home_lp,
            p_home_score - p_away_score
        );
        PERFORM public.increment_match_career_stats(
            v_away.discord_id, v_away_res,
            CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
            v_away_lp,
            p_away_score - p_home_score
        );

        UPDATE public.players
        SET pvp_ranked_matches = COALESCE(pvp_ranked_matches, 0) + 1
        WHERE discord_id IN (v_home.discord_id, v_away.discord_id);
    END IF;

    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        v_home.discord_id, v_home_res, p_home_rating, p_away_rating,
        p_home_score, p_away_score, v_home_coins,
        CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_away.discord_id, 'pvp', v_home_lp, FALSE
    ) RETURNING id INTO v_hist_home;

    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        v_away.discord_id, v_away_res, p_away_rating, p_home_rating,
        p_away_score, p_home_score, v_away_coins,
        CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_home.discord_id, 'pvp', v_away_lp, FALSE
    ) RETURNING id INTO v_hist_away;

    UPDATE public.match_runs
    SET status = 'completed',
        home_score = p_home_score,
        away_score = p_away_score,
        last_minute = 90,
        completed_at = NOW(),
        completion_key = p_run_id::TEXT,
        updated_at = NOW()
    WHERE id = p_run_id;

    IF v_home.discord_id < v_away.discord_id THEN
        v_id1 := v_home.discord_id; v_id2 := v_away.discord_id;
    ELSE
        v_id1 := v_away.discord_id; v_id2 := v_home.discord_id;
    END IF;
    PERFORM public.release_match_lock(v_id1);
    PERFORM public.release_match_lock(v_id2);

    RETURN jsonb_build_object(
        'ok', true,
        'run_id', p_run_id,
        'rewards_skipped', NOT v_rewards,
        'home', jsonb_build_object(
            'owner_id', v_home.discord_id,
            'result', v_home_res,
            'coins', v_home_coins,
            'lp_delta', v_home_lp,
            'history_id', v_hist_home,
            'rating', p_home_rating
        ),
        'away', jsonb_build_object(
            'owner_id', v_away.discord_id,
            'result', v_away_res,
            'coins', v_away_coins,
            'lp_delta', v_away_lp,
            'history_id', v_hist_away,
            'rating', p_away_rating
        )
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.finalize_pvp_match(UUID, INTEGER, INTEGER, NUMERIC, NUMERIC)
    TO anon, authenticated, service_role;

-- Practice finalize: capped rewards, forced zero LP, no rivalry
CREATE OR REPLACE FUNCTION public.finalize_ai_practice_match(
    p_run_id UUID,
    p_owner_id BIGINT,
    p_result TEXT,
    p_home_score INTEGER,
    p_away_score INTEGER,
    p_my_rating NUMERIC,
    p_opp_rating NUMERIC,
    p_is_new_manager BOOLEAN DEFAULT FALSE
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_player public.players%ROWTYPE;
    v_rewards BOOLEAN;
    v_cost INTEGER;
    v_mult NUMERIC;
    v_win_coins INTEGER;
    v_coins INTEGER := 0;
    v_hist UUID;
    v_daily INTEGER;
    v_cap INTEGER;
BEGIN
    IF p_result NOT IN ('win', 'draw', 'loss') THEN
        RAISE EXCEPTION 'Invalid result';
    END IF;

    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Match run not found';
    END IF;
    IF v_run.run_type NOT IN ('practice', 'bot') THEN
        RAISE EXCEPTION 'finalize_ai_practice_match requires practice/bot run';
    END IF;
    IF v_run.status = 'completed' THEN
        RETURN jsonb_build_object('ok', true, 'already', true, 'global_lp_delta', 0);
    END IF;

    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    v_rewards := COALESCE((public.get_game_config('ai_practice_rewards_enabled') #>> '{}')::BOOLEAN, TRUE);
    v_cost := public.get_game_config_int('ai_practice_energy_cost', 10)::INTEGER;
    v_cap := public.get_game_config_int('ai_practice_rewarded_daily', 2)::INTEGER;

    SELECT COUNT(*)::INTEGER INTO v_daily
    FROM public.match_history
    WHERE player_id = p_owner_id AND match_type = 'practice'
      AND (played_at AT TIME ZONE 'UTC')::DATE = (NOW() AT TIME ZONE 'UTC')::DATE;

    IF NOT p_is_new_manager AND v_daily >= v_cap THEN
        v_rewards := FALSE;
    END IF;

    v_mult := CASE WHEN p_is_new_manager
        THEN public.get_game_config_numeric('ai_practice_new_manager_reward_multiplier', 0.75)
        ELSE public.get_game_config_numeric('ai_practice_established_reward_multiplier', 0.50)
    END;

    SELECT win_coins INTO v_win_coins
    FROM public.global_divisions
    WHERE v_player.global_lp >= min_lp
    ORDER BY min_lp DESC LIMIT 1;
    v_win_coins := COALESCE(v_win_coins, 100);

    IF v_rewards THEN
        v_coins := GREATEST(0, FLOOR(
            CASE p_result
                WHEN 'win' THEN v_win_coins
                WHEN 'draw' THEN v_win_coins / 3
                ELSE GREATEST(15, v_win_coins / 10)
            END * v_mult
        )::INTEGER);
        PERFORM public.sync_action_energy(p_owner_id);
        PERFORM public.apply_club_economy(
            p_owner_id, v_coins, -v_cost,
            'match_practice_' || p_result,
            'match:' || p_run_id::TEXT || ':' || p_owner_id::TEXT,
            jsonb_build_object('match_type', 'practice', 'result', p_result, 'run_id', p_run_id)
        );
    ELSE
        -- Still charge energy if practicing past daily rewarded cap? Spec: capped rewards.
        -- Charge energy always for a completed practice.
        PERFORM public.sync_action_energy(p_owner_id);
        PERFORM public.apply_club_economy(
            p_owner_id, 0, -v_cost,
            'match_practice_' || p_result,
            'match:' || p_run_id::TEXT || ':' || p_owner_id::TEXT,
            jsonb_build_object('match_type', 'practice', 'result', p_result, 'run_id', p_run_id, 'rewarded', false)
        );
    END IF;

    -- Never touch global_lp / rivalry / competitive PvP record
    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        p_owner_id, p_result, p_my_rating, p_opp_rating,
        p_home_score, p_away_score, v_coins, 0, p_run_id, NULL, 'practice',
        0, FALSE
    ) RETURNING id INTO v_hist;

    UPDATE public.match_runs
    SET status = 'completed',
        home_score = p_home_score,
        away_score = p_away_score,
        completed_at = NOW(),
        completion_key = COALESCE(completion_key, p_run_id::TEXT),
        updated_at = NOW()
    WHERE id = p_run_id;

    PERFORM public.release_match_lock(p_owner_id);

    RETURN jsonb_build_object(
        'ok', true,
        'run_id', p_run_id,
        'history_id', v_hist,
        'coins', v_coins,
        'global_lp_delta', 0,
        'rivalry_counted', false,
        'rewards_skipped', NOT v_rewards
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.finalize_ai_practice_match(
    UUID, BIGINT, TEXT, INTEGER, INTEGER, NUMERIC, NUMERIC, BOOLEAN
) TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.finalize_pvp_match(uuid,integer,integer,numeric,numeric)') IS NULL THEN
        RAISE EXCEPTION '100 guard failed: finalize_pvp_match';
    END IF;
    IF to_regprocedure(
        'public.finalize_ai_practice_match(uuid,bigint,text,integer,integer,numeric,numeric,boolean)'
    ) IS NULL THEN
        RAISE EXCEPTION '100 guard failed: finalize_ai_practice_match';
    END IF;
END $$;

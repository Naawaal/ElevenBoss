-- Feature 053 US5/US6/US7: rivalry finalize, list/detail RPCs, blocks/prefs, stale matching reclaim

CREATE OR REPLACE FUNCTION public.reclaim_stale_pvp_matching(
    p_stale_seconds INTEGER DEFAULT 120
) RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_n INTEGER;
BEGIN
    UPDATE public.pvp_matchmaking_queue
    SET status = 'searching', claim_token = NULL, updated_at = NOW()
    WHERE status = 'matching'
      AND updated_at < NOW() - make_interval(secs => GREATEST(30, p_stale_seconds));
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN v_n;
END;
$$;

CREATE OR REPLACE FUNCTION public.set_pvp_block(
    p_blocker_id BIGINT,
    p_blocked_id BIGINT,
    p_blocked BOOLEAN DEFAULT TRUE
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    IF p_blocker_id = p_blocked_id THEN
        RAISE EXCEPTION 'Cannot block yourself';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.players WHERE discord_id = p_blocked_id) THEN
        RAISE EXCEPTION 'Player not found';
    END IF;
    IF p_blocked THEN
        INSERT INTO public.pvp_blocks (blocker_id, blocked_id)
        VALUES (p_blocker_id, p_blocked_id)
        ON CONFLICT DO NOTHING;
    ELSE
        DELETE FROM public.pvp_blocks
        WHERE blocker_id = p_blocker_id AND blocked_id = p_blocked_id;
    END IF;
    RETURN jsonb_build_object('ok', true, 'blocker_id', p_blocker_id, 'blocked_id', p_blocked_id, 'blocked', p_blocked);
END;
$$;

CREATE OR REPLACE FUNCTION public.set_pvp_prefs(
    p_owner_id BIGINT,
    p_rivalry_dms BOOLEAN DEFAULT NULL,
    p_rivalry_callouts BOOLEAN DEFAULT NULL,
    p_rivalry_lb_visible BOOLEAN DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.players
    SET
        pvp_rivalry_dms = COALESCE(p_rivalry_dms, pvp_rivalry_dms),
        pvp_rivalry_callouts = COALESCE(p_rivalry_callouts, pvp_rivalry_callouts),
        pvp_rivalry_lb_visible = COALESCE(p_rivalry_lb_visible, pvp_rivalry_lb_visible)
    WHERE discord_id = p_owner_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;
    RETURN jsonb_build_object('ok', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.managers_pvp_blocked(
    p_a BIGINT,
    p_b BIGINT
) RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.pvp_blocks
        WHERE (blocker_id = p_a AND blocked_id = p_b)
           OR (blocker_id = p_b AND blocked_id = p_a)
    );
$$;

CREATE OR REPLACE FUNCTION public._upsert_rivalry_from_pvp(
    p_home_id BIGINT,
    p_away_id BIGINT,
    p_home_score INTEGER,
    p_away_score INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_a BIGINT;
    v_b BIGINT;
    v_row public.manager_rivalries%ROWTYPE;
    v_winner BIGINT;
    v_meetings INTEGER;
    v_a_wins INTEGER;
    v_b_wins INTEGER;
    v_draws INTEGER;
    v_a_goals INTEGER;
    v_b_goals INTEGER;
    v_streak_owner BIGINT;
    v_streak_count INTEGER;
    v_status TEXT;
    v_activated TIMESTAMPTZ;
    v_window TIMESTAMPTZ;
    v_events JSONB := '[]'::JSONB;
    v_act_matches INTEGER;
    v_act_days INTEGER;
BEGIN
    IF p_home_id < p_away_id THEN
        v_a := p_home_id; v_b := p_away_id;
    ELSE
        v_a := p_away_id; v_b := p_home_id;
    END IF;

    IF p_home_score > p_away_score THEN
        v_winner := p_home_id;
    ELSIF p_home_score < p_away_score THEN
        v_winner := p_away_id;
    ELSE
        v_winner := NULL;
    END IF;

    v_act_matches := public.get_game_config_int('pvp_rivalry_activation_matches', 3)::INTEGER;
    v_act_days := public.get_game_config_int('pvp_rivalry_activation_days', 30)::INTEGER;

    SELECT * INTO v_row
    FROM public.manager_rivalries
    WHERE manager_a_id = v_a AND manager_b_id = v_b
    FOR UPDATE;

    IF NOT FOUND THEN
        v_meetings := 1;
        v_a_wins := CASE WHEN v_winner = v_a THEN 1 ELSE 0 END;
        v_b_wins := CASE WHEN v_winner = v_b THEN 1 ELSE 0 END;
        v_draws := CASE WHEN v_winner IS NULL THEN 1 ELSE 0 END;
        IF p_home_id = v_a THEN
            v_a_goals := p_home_score; v_b_goals := p_away_score;
        ELSE
            v_a_goals := p_away_score; v_b_goals := p_home_score;
        END IF;
        v_streak_owner := v_winner;
        v_streak_count := CASE WHEN v_winner IS NULL THEN 0 ELSE 1 END;
        v_status := 'tracking';
        v_activated := NULL;
        v_window := NOW();
        INSERT INTO public.manager_rivalries (
            manager_a_id, manager_b_id, meetings, a_wins, b_wins, draws,
            a_goals, b_goals, current_streak_owner, current_streak_count,
            longest_streak_owner, longest_streak_count, last_winner_id,
            last_result, last_match_at, first_meeting_in_window_at, status
        ) VALUES (
            v_a, v_b, v_meetings, v_a_wins, v_b_wins, v_draws,
            v_a_goals, v_b_goals, v_streak_owner, v_streak_count,
            v_streak_owner, v_streak_count, v_winner,
            CASE WHEN v_winner IS NULL THEN 'draw' WHEN v_winner = v_a THEN 'a_win' ELSE 'b_win' END,
            NOW(), v_window, v_status
        );
    ELSE
        v_meetings := v_row.meetings + 1;
        v_a_wins := v_row.a_wins + CASE WHEN v_winner = v_a THEN 1 ELSE 0 END;
        v_b_wins := v_row.b_wins + CASE WHEN v_winner = v_b THEN 1 ELSE 0 END;
        v_draws := v_row.draws + CASE WHEN v_winner IS NULL THEN 1 ELSE 0 END;
        IF p_home_id = v_a THEN
            v_a_goals := v_row.a_goals + p_home_score;
            v_b_goals := v_row.b_goals + p_away_score;
        ELSE
            v_a_goals := v_row.a_goals + p_away_score;
            v_b_goals := v_row.b_goals + p_home_score;
        END IF;

        IF v_winner IS NULL THEN
            v_streak_owner := NULL;
            v_streak_count := 0;
        ELSIF v_winner = v_row.current_streak_owner THEN
            v_streak_owner := v_winner;
            v_streak_count := v_row.current_streak_count + 1;
        ELSE
            IF v_row.current_streak_owner IS NOT NULL AND v_row.current_streak_count >= 3 THEN
                v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'streak_broken'), jsonb_build_object('code', 'revenge_served'));
            END IF;
            v_streak_owner := v_winner;
            v_streak_count := 1;
        END IF;

        v_window := v_row.first_meeting_in_window_at;
        IF v_window IS NULL OR (NOW() - v_window) > make_interval(days => v_act_days) THEN
            v_window := NOW();
        END IF;

        v_status := v_row.status;
        v_activated := v_row.activated_at;
        IF v_status = 'dormant' THEN
            v_status := 'tracking';
        END IF;
        IF v_status IN ('tracking', 'dormant')
           AND v_meetings >= v_act_matches
           AND (NOW() - v_window) <= make_interval(days => v_act_days) THEN
            v_status := 'active';
            v_activated := NOW();
            v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'rivalry_activated', 'message', 'Third ranked meeting — rivalry activated.'));
        END IF;

        IF v_a_wins = v_b_wins AND v_meetings >= 2 THEN
            v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'series_tied'));
        END IF;
        IF v_streak_count = 3 THEN
            v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'three_win_streak'));
        END IF;
        IF v_meetings = 5 THEN
            v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'fifth_meeting'));
        END IF;
        IF v_meetings = 10 THEN
            v_events := v_events || jsonb_build_array(jsonb_build_object('code', 'tenth_meeting'));
        END IF;

        UPDATE public.manager_rivalries SET
            meetings = v_meetings,
            a_wins = v_a_wins,
            b_wins = v_b_wins,
            draws = v_draws,
            a_goals = v_a_goals,
            b_goals = v_b_goals,
            current_streak_owner = v_streak_owner,
            current_streak_count = v_streak_count,
            longest_streak_owner = CASE
                WHEN v_streak_count > longest_streak_count THEN v_streak_owner
                ELSE longest_streak_owner END,
            longest_streak_count = GREATEST(longest_streak_count, v_streak_count),
            last_winner_id = v_winner,
            last_result = CASE WHEN v_winner IS NULL THEN 'draw' WHEN v_winner = v_a THEN 'a_win' ELSE 'b_win' END,
            last_match_at = NOW(),
            first_meeting_in_window_at = v_window,
            status = v_status,
            activated_at = v_activated,
            updated_at = NOW()
        WHERE manager_a_id = v_a AND manager_b_id = v_b;
    END IF;

    -- Badge keys on both managers for activation / revenge
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_events) e WHERE e->>'code' = 'rivalry_activated') THEN
        UPDATE public.players
        SET pvp_badge_keys = CASE
            WHEN NOT ('first_rival' = ANY(pvp_badge_keys)) THEN array_append(pvp_badge_keys, 'first_rival')
            ELSE pvp_badge_keys END
        WHERE discord_id IN (v_a, v_b);
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_events) e WHERE e->>'code' = 'revenge_served') THEN
        UPDATE public.players
        SET pvp_badge_keys = CASE
            WHEN NOT ('revenge_served' = ANY(pvp_badge_keys)) THEN array_append(pvp_badge_keys, 'revenge_served')
            ELSE pvp_badge_keys END
        WHERE discord_id = v_winner;
    END IF;

    RETURN jsonb_build_object(
        'manager_a_id', v_a,
        'manager_b_id', v_b,
        'meetings', v_meetings,
        'a_wins', v_a_wins,
        'b_wins', v_b_wins,
        'draws', v_draws,
        'status', v_status,
        'events', v_events
    );
END;
$$;

-- Patch finalize_pvp_match: after history inserts, rivalry update when flagged
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
    v_rivalries BOOLEAN;
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
    v_id1 BIGINT;
    v_id2 BIGINT;
    v_rivalry JSONB := NULL;
BEGIN
    SELECT * INTO v_run FROM public.match_runs WHERE id = p_run_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Match run not found'; END IF;
    IF v_run.run_type <> 'pvp' THEN RAISE EXCEPTION 'finalize_pvp_match requires run_type=pvp'; END IF;

    IF v_run.status = 'completed' THEN
        RETURN jsonb_build_object(
            'ok', true, 'already', true, 'run_id', p_run_id,
            'home', jsonb_build_object('coins', 0, 'lp_delta', 0),
            'away', jsonb_build_object('coins', 0, 'lp_delta', 0)
        );
    END IF;
    IF v_run.status NOT IN ('streaming', 'completing') THEN
        RAISE EXCEPTION 'Run not finalizable (status=%)', v_run.status;
    END IF;

    UPDATE public.match_runs SET status = 'completing', updated_at = NOW() WHERE id = p_run_id;

    SELECT * INTO v_home FROM public.players WHERE discord_id = v_run.home_discord_id FOR UPDATE;
    SELECT * INTO v_away FROM public.players WHERE discord_id = v_run.away_discord_id FOR UPDATE;
    IF v_home.discord_id IS NULL OR v_away.discord_id IS NULL THEN
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
    v_rivalries := COALESCE((public.get_game_config('pvp_rivalries_enabled') #>> '{}')::BOOLEAN, FALSE)
                   AND public._pvp_flag_on();
    v_cost := public.get_game_config_int('pvp_energy_cost', 20)::INTEGER;
    v_prov := public.get_game_config_int('pvp_provisional_matches', 5)::INTEGER;

    SELECT win_coins INTO v_home_win_coins FROM public.global_divisions
    WHERE v_home.global_lp >= min_lp ORDER BY min_lp DESC LIMIT 1;
    SELECT win_coins INTO v_away_win_coins FROM public.global_divisions
    WHERE v_away.global_lp >= min_lp ORDER BY min_lp DESC LIMIT 1;
    v_home_win_coins := COALESCE(v_home_win_coins, 100);
    v_away_win_coins := COALESCE(v_away_win_coins, 100);

    IF v_rewards THEN
        v_mult := CASE v_home_res
            WHEN 'win' THEN public.get_game_config_numeric('pvp_coin_multiplier_win', 1.25)
            WHEN 'draw' THEN public.get_game_config_numeric('pvp_coin_multiplier_draw', 1.10)
            ELSE public.get_game_config_numeric('pvp_coin_multiplier_loss', 1.00) END;
        v_home_coins := GREATEST(0, FLOOR(CASE v_home_res
            WHEN 'win' THEN v_home_win_coins WHEN 'draw' THEN v_home_win_coins / 3
            ELSE GREATEST(15, v_home_win_coins / 10) END * v_mult)::INTEGER);
        v_mult := CASE v_away_res
            WHEN 'win' THEN public.get_game_config_numeric('pvp_coin_multiplier_win', 1.25)
            WHEN 'draw' THEN public.get_game_config_numeric('pvp_coin_multiplier_draw', 1.10)
            ELSE public.get_game_config_numeric('pvp_coin_multiplier_loss', 1.00) END;
        v_away_coins := GREATEST(0, FLOOR(CASE v_away_res
            WHEN 'win' THEN v_away_win_coins WHEN 'draw' THEN v_away_win_coins / 3
            ELSE GREATEST(15, v_away_win_coins / 10) END * v_mult)::INTEGER);

        PERFORM public.sync_action_energy(v_home.discord_id);
        PERFORM public.sync_action_energy(v_away.discord_id);
        PERFORM public.apply_club_economy(v_home.discord_id, v_home_coins, -v_cost, 'match_pvp_' || v_home_res,
            'match:' || p_run_id::TEXT || ':' || v_home.discord_id::TEXT,
            jsonb_build_object('match_type', 'pvp', 'result', v_home_res, 'run_id', p_run_id));
        PERFORM public.apply_club_economy(v_away.discord_id, v_away_coins, -v_cost, 'match_pvp_' || v_away_res,
            'match:' || p_run_id::TEXT || ':' || v_away.discord_id::TEXT,
            jsonb_build_object('match_type', 'pvp', 'result', v_away_res, 'run_id', p_run_id));

        v_raw_lp := CASE v_home_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_home_res = 'loss' AND COALESCE(v_home.pvp_ranked_matches, 0) < v_prov THEN v_raw_lp := v_raw_lp / 2; END IF;
        v_new_lp := GREATEST(0, v_home.global_lp + v_raw_lp);
        v_home_lp := v_new_lp - v_home.global_lp;

        v_raw_lp := CASE v_away_res WHEN 'win' THEN 15 WHEN 'draw' THEN 5 ELSE -10 END;
        IF v_away_res = 'loss' AND COALESCE(v_away.pvp_ranked_matches, 0) < v_prov THEN v_raw_lp := v_raw_lp / 2; END IF;
        v_new_lp := GREATEST(0, v_away.global_lp + v_raw_lp);
        v_away_lp := v_new_lp - v_away.global_lp;

        PERFORM public.increment_match_career_stats(v_home.discord_id, v_home_res,
            CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END, v_home_lp, p_home_score - p_away_score);
        PERFORM public.increment_match_career_stats(v_away.discord_id, v_away_res,
            CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END, v_away_lp, p_away_score - p_home_score);
        UPDATE public.players SET pvp_ranked_matches = COALESCE(pvp_ranked_matches, 0) + 1
        WHERE discord_id IN (v_home.discord_id, v_away.discord_id);
    END IF;

    IF v_rivalries THEN
        v_rivalry := public._upsert_rivalry_from_pvp(
            v_home.discord_id, v_away.discord_id, p_home_score, p_away_score
        );
    END IF;

    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        v_home.discord_id, v_home_res, p_home_rating, p_away_rating,
        p_home_score, p_away_score, v_home_coins,
        CASE v_home_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_away.discord_id, 'pvp', v_home_lp, v_rivalries
    ) RETURNING id INTO v_hist_home;

    INSERT INTO public.match_history (
        player_id, result, my_rating, opponent_rating, goals_for, goals_against,
        coins_earned, points_earned, run_id, opponent_owner_id, match_type,
        global_lp_delta, rivalry_counted
    ) VALUES (
        v_away.discord_id, v_away_res, p_away_rating, p_home_rating,
        p_away_score, p_home_score, v_away_coins,
        CASE v_away_res WHEN 'win' THEN 3 WHEN 'draw' THEN 1 ELSE 0 END,
        p_run_id, v_home.discord_id, 'pvp', v_away_lp, v_rivalries
    ) RETURNING id INTO v_hist_away;

    UPDATE public.match_runs SET
        status = 'completed', home_score = p_home_score, away_score = p_away_score,
        last_minute = 90, completed_at = NOW(), completion_key = p_run_id::TEXT, updated_at = NOW()
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
        'rivalry', v_rivalry,
        'home', jsonb_build_object(
            'owner_id', v_home.discord_id, 'result', v_home_res, 'coins', v_home_coins,
            'lp_delta', v_home_lp, 'history_id', v_hist_home, 'rating', p_home_rating
        ),
        'away', jsonb_build_object(
            'owner_id', v_away.discord_id, 'result', v_away_res, 'coins', v_away_coins,
            'lp_delta', v_away_lp, 'history_id', v_hist_away, 'rating', p_away_rating
        )
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_manager_rivalries(p_owner_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_out JSONB;
BEGIN
    -- Dormancy refresh (read-time soft)
    UPDATE public.manager_rivalries
    SET status = 'dormant', updated_at = NOW()
    WHERE status IN ('active', 'tracking')
      AND (manager_a_id = p_owner_id OR manager_b_id = p_owner_id)
      AND last_match_at < NOW() - make_interval(
          days => public.get_game_config_int('pvp_rivalry_dormant_days', 60)::INTEGER
      );

    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'manager_a_id', r.manager_a_id,
        'manager_b_id', r.manager_b_id,
        'opponent_id', CASE WHEN r.manager_a_id = p_owner_id THEN r.manager_b_id ELSE r.manager_a_id END,
        'meetings', r.meetings,
        'my_wins', CASE WHEN r.manager_a_id = p_owner_id THEN r.a_wins ELSE r.b_wins END,
        'their_wins', CASE WHEN r.manager_a_id = p_owner_id THEN r.b_wins ELSE r.a_wins END,
        'draws', r.draws,
        'status', r.status,
        'current_streak_owner', r.current_streak_owner,
        'current_streak_count', r.current_streak_count,
        'last_match_at', r.last_match_at
    ) ORDER BY r.last_match_at DESC), '[]'::JSONB)
    INTO v_out
    FROM public.manager_rivalries r
    WHERE r.manager_a_id = p_owner_id OR r.manager_b_id = p_owner_id;

    RETURN jsonb_build_object('rivalries', v_out);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_rivalry_detail(
    p_viewer_id BIGINT,
    p_opponent_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
DECLARE
    v_a BIGINT;
    v_b BIGINT;
    v_row public.manager_rivalries%ROWTYPE;
    v_recent JSONB;
    v_viewer public.players%ROWTYPE;
BEGIN
    IF p_viewer_id < p_opponent_id THEN v_a := p_viewer_id; v_b := p_opponent_id;
    ELSE v_a := p_opponent_id; v_b := p_viewer_id; END IF;

    SELECT * INTO v_row FROM public.manager_rivalries
    WHERE manager_a_id = v_a AND manager_b_id = v_b;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('found', false);
    END IF;

    SELECT * INTO v_viewer FROM public.players WHERE discord_id = p_viewer_id;

    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'result', mh.result,
        'goals_for', mh.goals_for,
        'goals_against', mh.goals_against,
        'played_at', mh.played_at,
        'lp_delta', mh.global_lp_delta
    ) ORDER BY mh.played_at DESC), '[]'::JSONB)
    INTO v_recent
    FROM (
        SELECT * FROM public.match_history
        WHERE player_id = p_viewer_id AND opponent_owner_id = p_opponent_id AND match_type = 'pvp'
        ORDER BY played_at DESC LIMIT 5
    ) mh;

    RETURN jsonb_build_object(
        'found', true,
        'manager_a_id', v_row.manager_a_id,
        'manager_b_id', v_row.manager_b_id,
        'meetings', v_row.meetings,
        'a_wins', v_row.a_wins,
        'b_wins', v_row.b_wins,
        'draws', v_row.draws,
        'a_goals', v_row.a_goals,
        'b_goals', v_row.b_goals,
        'status', v_row.status,
        'current_streak_owner', v_row.current_streak_owner,
        'current_streak_count', v_row.current_streak_count,
        'longest_streak_owner', v_row.longest_streak_owner,
        'longest_streak_count', v_row.longest_streak_count,
        'last_match_at', v_row.last_match_at,
        'recent', v_recent,
        'viewer_badges', COALESCE(to_jsonb(v_viewer.pvp_badge_keys), '[]'::JSONB),
        'prefs', jsonb_build_object(
            'dms', v_viewer.pvp_rivalry_dms,
            'callouts', v_viewer.pvp_rivalry_callouts,
            'lb_visible', v_viewer.pvp_rivalry_lb_visible
        ),
        'blocked', public.managers_pvp_blocked(p_viewer_id, p_opponent_id)
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_server_hottest_rivalries(
    p_guild_id BIGINT,
    p_limit INTEGER DEFAULT 10
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
DECLARE
    v_out JSONB;
BEGIN
    -- Guild-local approximation: rivalries where both managers have a recent PvP in this guild's match_runs
    SELECT COALESCE(jsonb_agg(row_to_json(t)::JSONB), '[]'::JSONB)
    INTO v_out
    FROM (
        SELECT
            r.manager_a_id,
            r.manager_b_id,
            r.meetings,
            r.a_wins,
            r.b_wins,
            r.draws,
            r.last_match_at,
            (
                SELECT COUNT(*) FROM public.match_history mh
                WHERE mh.match_type = 'pvp'
                  AND mh.player_id = r.manager_a_id
                  AND mh.opponent_owner_id = r.manager_b_id
                  AND mh.played_at > NOW() - INTERVAL '30 days'
            ) AS meetings_30d
        FROM public.manager_rivalries r
        WHERE r.status IN ('active', 'tracking')
          AND EXISTS (
              SELECT 1 FROM public.players pa WHERE pa.discord_id = r.manager_a_id AND COALESCE(pa.pvp_rivalry_lb_visible, TRUE)
          )
          AND EXISTS (
              SELECT 1 FROM public.players pb WHERE pb.discord_id = r.manager_b_id AND COALESCE(pb.pvp_rivalry_lb_visible, TRUE)
          )
        ORDER BY meetings_30d DESC, ABS(r.a_wins - r.b_wins) ASC, r.last_match_at DESC
        LIMIT GREATEST(1, LEAST(p_limit, 25))
    ) t;

    RETURN jsonb_build_object('guild_id', p_guild_id, 'rivalries', v_out);
END;
$$;

GRANT EXECUTE ON FUNCTION public.reclaim_stale_pvp_matching(INTEGER) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.set_pvp_block(BIGINT, BIGINT, BOOLEAN) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.set_pvp_prefs(BIGINT, BOOLEAN, BOOLEAN, BOOLEAN) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.managers_pvp_blocked(BIGINT, BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_manager_rivalries(BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_rivalry_detail(BIGINT, BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_server_hottest_rivalries(BIGINT, INTEGER) TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.set_pvp_block(bigint,bigint,boolean)') IS NULL THEN
        RAISE EXCEPTION '101 guard failed: set_pvp_block';
    END IF;
    IF to_regprocedure('public.get_manager_rivalries(bigint)') IS NULL THEN
        RAISE EXCEPTION '101 guard failed: get_manager_rivalries';
    END IF;
END $$;

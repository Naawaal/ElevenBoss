-- US-38 remediation: economy idempotency, lock RPCs, career stats, admin RPC hardening,
-- legacy RPC removal, match XP idempotency, SECURITY DEFINER on economy pipes.

-- ---------------------------------------------------------------------------
-- C2: Drop legacy economy bypass (if still present from 002)
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.process_training_start(BIGINT, UUID, TEXT, BIGINT, NUMERIC);
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'process_training_start'
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM anon, authenticated', r.sig);
        EXECUTE format('DROP FUNCTION IF EXISTS %s', r.sig);
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- C1: apply_club_economy — idempotency re-check after FOR UPDATE; rollback on conflict
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
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_existing RECORD;
    v_coins BIGINT;
    v_energy INTEGER;
    v_max INTEGER;
    v_new_coins BIGINT;
    v_new_energy INTEGER;
BEGIN
    PERFORM public.sync_action_energy(p_club_id);

    SELECT coins, action_energy
    INTO v_coins, v_energy
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

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

    BEGIN
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
-- H2: Atomic match lock acquire / release
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.acquire_match_lock(
    p_discord_id BIGINT,
    p_lock_type TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_inserted BIGINT;
BEGIN
    IF p_lock_type NOT IN ('friendly', 'league', 'bot') THEN
        RAISE EXCEPTION 'Invalid lock_type: %', p_lock_type;
    END IF;
    INSERT INTO public.match_locks (discord_id, lock_type)
    VALUES (p_discord_id, p_lock_type)
    ON CONFLICT (discord_id) DO NOTHING
    RETURNING discord_id INTO v_inserted;
    RETURN v_inserted IS NOT NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.release_match_lock(p_discord_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM public.match_locks WHERE discord_id = p_discord_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.acquire_match_lock(BIGINT, TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.release_match_lock(BIGINT) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- H3: Atomic career stat increments
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.increment_match_career_stats(
    p_club_id BIGINT,
    p_result TEXT,
    p_league_points_delta INTEGER DEFAULT 0,
    p_lp_change INTEGER DEFAULT 0,
    p_goal_diff_delta INTEGER DEFAULT 0
) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE public.players
    SET
        league_points = league_points + COALESCE(p_league_points_delta, 0),
        global_lp = GREATEST(0, global_lp + COALESCE(p_lp_change, 0)),
        goal_difference = goal_difference + COALESCE(p_goal_diff_delta, 0),
        matches_played = matches_played + 1,
        wins = wins + CASE WHEN p_result = 'win' THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN p_result = 'draw' THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN p_result = 'loss' THEN 1 ELSE 0 END
    WHERE discord_id = p_club_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.increment_league_career_stats(
    p_club_id BIGINT,
    p_result TEXT
) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE public.players
    SET
        matches_played = matches_played + 1,
        wins = wins + CASE WHEN p_result = 'win' THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN p_result = 'draw' THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN p_result = 'loss' THEN 1 ELSE 0 END
    WHERE discord_id = p_club_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.increment_match_career_stats(BIGINT, TEXT, INTEGER, INTEGER, INTEGER) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.increment_league_career_stats(BIGINT, TEXT) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- H5: renew_contract via apply_club_economy
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.renew_contract(
    p_club_id BIGINT,
    p_card_id UUID,
    p_cost BIGINT,
    p_extension_days INTEGER
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_expiry TIMESTAMPTZ;
    v_age INTEGER;
    v_warn INTEGER;
    v_dob DATE;
    v_econ JSONB;
BEGIN
    v_warn := public.get_game_config_int('retirement_warning_age', 35)::INTEGER;

    IF NOT EXISTS (
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_club_id AND COALESCE(is_retired, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    SELECT date_of_birth INTO v_dob FROM public.player_cards WHERE id = p_card_id;
    v_age := public.card_age_from_dob(v_dob);
    IF v_age >= v_warn THEN
        RAISE EXCEPTION 'Cannot renew contract for players age % and over', v_warn;
    END IF;

    v_econ := public.apply_club_economy(
        p_club_id,
        -p_cost,
        0,
        'contract_renewal',
        'contract_renewal:' || p_card_id::TEXT,
        jsonb_build_object('card_id', p_card_id, 'extension_days', p_extension_days)
    );

    IF COALESCE((v_econ->>'replay')::BOOLEAN, FALSE) THEN
        RETURN TRUE;
    END IF;

    SELECT contract_expires_at INTO v_expiry FROM public.player_cards WHERE id = p_card_id;
    IF v_expiry IS NULL OR v_expiry < NOW() THEN
        v_expiry := NOW();
    END IF;

    UPDATE public.player_cards
    SET contract_expires_at = v_expiry + (p_extension_days * INTERVAL '1 day')
    WHERE id = p_card_id;

    RETURN TRUE;
END;
$$;

-- ---------------------------------------------------------------------------
-- H5: cancel_player_evolution via apply_club_economy
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.cancel_player_evolution(
    p_owner_id BIGINT,
    p_evo_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_evo RECORD;
    v_fee CONSTANT INTEGER := 100;
    v_econ JSONB;
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

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_fee,
        0,
        'evolution_cancel',
        'evolution_cancel:' || p_evo_id::TEXT,
        jsonb_build_object('evo_id', p_evo_id)
    );

    IF COALESCE((v_econ->>'replay')::BOOLEAN, FALSE) THEN
        RETURN jsonb_build_object('cancelled', TRUE, 'fee', v_fee, 'replay', TRUE);
    END IF;

    UPDATE public.active_evolutions
    SET
        status = 'cancelled',
        cancelled_at = NOW(),
        matches_played = 0,
        current_progress = 0
    WHERE id = p_evo_id;

    RETURN jsonb_build_object('cancelled', TRUE, 'fee', v_fee);
END;
$$;

-- ---------------------------------------------------------------------------
-- H6: process_match_result — optional match_history idempotency
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.process_match_result(text, uuid[], integer, numeric[]);
DROP FUNCTION IF EXISTS public.process_match_result(text, uuid[], integer, numeric[], integer[]);

CREATE OR REPLACE FUNCTION public.process_match_result(
    p_result TEXT,
    p_card_ids UUID[],
    p_xp_amount INTEGER,
    p_card_ratings NUMERIC[] DEFAULT NULL,
    p_xp_amounts INTEGER[] DEFAULT NULL,
    p_match_history_id UUID DEFAULT NULL
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
    v_xp INTEGER;
    v_dob DATE;
    v_xp_applied TIMESTAMPTZ;
BEGIN
    IF p_match_history_id IS NOT NULL THEN
        SELECT xp_applied_at INTO v_xp_applied
        FROM public.match_history
        WHERE id = p_match_history_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'match_history row not found';
        END IF;
        IF v_xp_applied IS NOT NULL THEN
            RETURN TRUE;
        END IF;
    END IF;

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

        SELECT date_of_birth, potential, base_potential, recent_match_ratings
        INTO v_dob, v_pot, v_init_pot, v_recent
        FROM public.player_cards
        WHERE id = v_card_id AND COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE;

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        v_age := public.card_age_from_dob(v_dob);

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
                age = v_age,
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta)),
                recent_match_ratings = v_recent,
                potential = v_pot
            WHERE id = v_card_id;
        ELSE
            UPDATE public.player_cards
            SET
                age = v_age,
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta))
            WHERE id = v_card_id;
        END IF;

        v_xp := p_xp_amount;
        IF p_xp_amounts IS NOT NULL AND array_length(p_xp_amounts, 1) >= v_i THEN
            v_xp := p_xp_amounts[v_i];
        END IF;

        PERFORM public.apply_card_xp(v_card_id, v_xp, 'match_simulation');
    END LOOP;

    PERFORM public.tick_evolution_match_progress(p_card_ids);

    IF p_match_history_id IS NOT NULL THEN
        UPDATE public.match_history
        SET xp_applied_at = NOW()
        WHERE id = p_match_history_id;
    END IF;

    RETURN TRUE;
END;
$$;

GRANT EXECUTE ON FUNCTION public.process_match_result(TEXT, UUID[], INTEGER, NUMERIC[], INTEGER[], UUID) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- M9: Atomic matchday milestone points aggregation
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.upsert_matchday_milestone_points(
    p_season_id UUID,
    p_player_id BIGINT,
    p_matchday INTEGER,
    p_points_delta INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_row public.league_matchday_milestones%ROWTYPE;
BEGIN
    INSERT INTO public.league_matchday_milestones (
        season_id, player_id, matchday, points_earned, milestone_claimed
    ) VALUES (
        p_season_id, p_player_id, p_matchday, GREATEST(0, p_points_delta), FALSE
    )
    ON CONFLICT (season_id, player_id, matchday)
    DO UPDATE SET points_earned = public.league_matchday_milestones.points_earned + GREATEST(0, p_points_delta)
    RETURNING * INTO v_row;

    RETURN jsonb_build_object(
        'points_earned', v_row.points_earned,
        'milestone_claimed', v_row.milestone_claimed
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_matchday_milestone_points(UUID, BIGINT, INTEGER, INTEGER) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- H4: Revoke anon/authenticated on admin-only RPCs
-- ---------------------------------------------------------------------------
REVOKE EXECUTE ON FUNCTION public.distribute_season_prizes(UUID) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.charge_league_entry_fees(UUID) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.process_season_aging() FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.distribute_season_prizes(UUID) TO service_role;
GRANT EXECUTE ON FUNCTION public.charge_league_entry_fees(UUID) TO service_role;
GRANT EXECUTE ON FUNCTION public.process_season_aging() TO service_role;

-- ponytail: insert_scouting_pool_player signature may vary — revoke all overloads
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'insert_scouting_pool_player'
    LOOP
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM anon, authenticated', r.sig);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', r.sig);
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- C3 (partial): Revoke direct ledger writes from anon; RPC is SECURITY DEFINER
-- ---------------------------------------------------------------------------
REVOKE INSERT, UPDATE, DELETE ON TABLE public.economy_ledger FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.player_xp_log FROM anon, authenticated;

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
            ('function:public.acquire_match_lock'),
            ('function:public.release_match_lock'),
            ('function:public.increment_match_career_stats'),
            ('function:public.increment_league_career_stats'),
            ('function:public.upsert_matchday_milestone_points'),
            ('function:public.process_match_result'),
            ('function:public.renew_contract'),
            ('function:public.cancel_player_evolution')
    ) AS req(obj)
    WHERE NOT (
        req.obj = 'function:public.acquire_match_lock'
            AND to_regprocedure('public.acquire_match_lock(bigint,text)') IS NOT NULL
        OR req.obj = 'function:public.release_match_lock'
            AND to_regprocedure('public.release_match_lock(bigint)') IS NOT NULL
        OR req.obj = 'function:public.increment_match_career_stats'
            AND to_regprocedure('public.increment_match_career_stats(bigint,text,integer,integer,integer)') IS NOT NULL
        OR req.obj = 'function:public.increment_league_career_stats'
            AND to_regprocedure('public.increment_league_career_stats(bigint,text)') IS NOT NULL
        OR req.obj = 'function:public.upsert_matchday_milestone_points'
            AND to_regprocedure('public.upsert_matchday_milestone_points(uuid,bigint,integer,integer)') IS NOT NULL
        OR req.obj = 'function:public.process_match_result'
            AND to_regprocedure('public.process_match_result(text,uuid[],integer,numeric[],integer[],uuid)') IS NOT NULL
        OR req.obj = 'function:public.renew_contract'
            AND to_regprocedure('public.renew_contract(bigint,uuid,bigint,integer)') IS NOT NULL
        OR req.obj = 'function:public.cancel_player_evolution'
            AND to_regprocedure('public.cancel_player_evolution(bigint,uuid)') IS NOT NULL
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '047_audit_remediation guard failed — missing: %', v_missing;
    END IF;
END;
$$;

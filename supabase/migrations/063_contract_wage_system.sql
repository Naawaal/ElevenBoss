-- 063: Contract & wage system (feature flag default off)
-- Spec: specs/019-contract-wage-system/

-- ---------------------------------------------------------------------------
-- Players payroll state
-- ---------------------------------------------------------------------------

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS payroll_debt BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS payroll_strikes INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_payroll_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_payroll_week TEXT;

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_payroll_debt_nonneg;
ALTER TABLE public.players
    ADD CONSTRAINT players_payroll_debt_nonneg CHECK (payroll_debt >= 0);

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_payroll_strikes_nonneg;
ALTER TABLE public.players
    ADD CONSTRAINT players_payroll_strikes_nonneg CHECK (payroll_strikes >= 0);

-- ---------------------------------------------------------------------------
-- Payroll runs (idempotency + audit)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.payroll_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id       BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    week_key      TEXT NOT NULL,
    bill_coins    BIGINT NOT NULL DEFAULT 0,
    debt_before   BIGINT NOT NULL DEFAULT 0,
    paid_coins    BIGINT NOT NULL DEFAULT 0,
    debt_after    BIGINT NOT NULL DEFAULT 0,
    strikes_after INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL
                  CHECK (status IN (
                      'paid', 'partial', 'skipped_flag', 'skipped_ai', 'skipped_zero'
                  )),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (club_id, week_key)
);

CREATE INDEX IF NOT EXISTS payroll_runs_week_key_idx
    ON public.payroll_runs (week_key);

CREATE INDEX IF NOT EXISTS payroll_runs_club_created_idx
    ON public.payroll_runs (club_id, created_at DESC);

ALTER TABLE public.payroll_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS payroll_runs_select ON public.payroll_runs;
CREATE POLICY payroll_runs_select ON public.payroll_runs
    FOR SELECT TO anon, authenticated, service_role
    USING (true);

DROP POLICY IF EXISTS payroll_runs_insert ON public.payroll_runs;
CREATE POLICY payroll_runs_insert ON public.payroll_runs
    FOR INSERT TO anon, authenticated, service_role
    WITH CHECK (true);

DROP POLICY IF EXISTS payroll_runs_update ON public.payroll_runs;
CREATE POLICY payroll_runs_update ON public.payroll_runs
    FOR UPDATE TO anon, authenticated, service_role
    USING (true)
    WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- Config
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('wages_payroll_enabled', 'false'),
    ('wages_payroll_bill_scale', '1.0'),
    ('wage_scale_factor', '1.2'),
    ('wage_rarity_mult_common', '1.0'),
    ('wage_rarity_mult_rare', '1.05'),
    ('wage_rarity_mult_epic', '1.10'),
    ('wage_rarity_mult_legendary', '1.15'),
    ('wage_age_mult_enabled', 'false'),
    ('wage_pot_mult_enabled', 'false'),
    ('contract_renewal_days', '7'),
    ('contract_grace_days', '7'),
    ('payroll_strike_friendly_block', '2'),
    ('payroll_strike_market_block', '3')
ON CONFLICT (key) DO NOTHING;

UPDATE public.player_cards
SET contract_expires_at = NOW() + INTERVAL '30 days'
WHERE contract_expires_at IS NULL;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.wages_payroll_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('wages_payroll_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

CREATE OR REPLACE FUNCTION public.payroll_utc_week_key(p_ts TIMESTAMPTZ DEFAULT NOW())
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
    SELECT to_char(p_ts AT TIME ZONE 'UTC', 'IYYY')
        || '-W'
        || to_char(p_ts AT TIME ZONE 'UTC', 'IW');
$$;

CREATE OR REPLACE FUNCTION public.card_weekly_wage_coins(
    p_overall INTEGER,
    p_rarity TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_scale NUMERIC;
    v_ovr INTEGER;
    v_base NUMERIC;
    v_mult NUMERIC;
    v_rarity TEXT := COALESCE(p_rarity, 'Common');
BEGIN
    v_scale := COALESCE(
        (public.get_game_config('wage_scale_factor') #>> '{}')::NUMERIC,
        1.2
    );
    v_ovr := GREATEST(40, COALESCE(p_overall, 50));
    v_base := (v_ovr - 40)^2 * v_scale + 10;

    v_mult := CASE lower(v_rarity)
        WHEN 'rare' THEN COALESCE(
            (public.get_game_config('wage_rarity_mult_rare') #>> '{}')::NUMERIC, 1.05)
        WHEN 'epic' THEN COALESCE(
            (public.get_game_config('wage_rarity_mult_epic') #>> '{}')::NUMERIC, 1.10)
        WHEN 'legendary' THEN COALESCE(
            (public.get_game_config('wage_rarity_mult_legendary') #>> '{}')::NUMERIC, 1.15)
        ELSE COALESCE(
            (public.get_game_config('wage_rarity_mult_common') #>> '{}')::NUMERIC, 1.0)
    END;

    RETURN floor(v_base * v_mult)::BIGINT;
END;
$$;

CREATE OR REPLACE FUNCTION public.club_xi_weekly_wage_bill(p_club_id BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_sum BIGINT := 0;
    v_scale NUMERIC;
BEGIN
    SELECT COALESCE(SUM(public.card_weekly_wage_coins(pc.overall, pc.rarity)), 0)
    INTO v_sum
    FROM public.squad_assignments sa
    JOIN public.player_cards pc ON pc.id = sa.player_card_id
    WHERE sa.discord_id = p_club_id;

    v_scale := COALESCE(
        (public.get_game_config('wages_payroll_bill_scale') #>> '{}')::NUMERIC,
        1.0
    );
    RETURN floor(v_sum * v_scale)::BIGINT;
END;
$$;

CREATE OR REPLACE FUNCTION public.card_contract_blocks_xi(p_expires TIMESTAMPTZ)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT CASE
        WHEN p_expires IS NULL THEN FALSE
        ELSE NOW() >= (
            p_expires
            + make_interval(
                days => public.get_game_config_int('contract_grace_days', 7)::INTEGER
              )
        )
    END;
$$;

CREATE OR REPLACE FUNCTION public.assert_club_payroll_market_ok(p_club_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_strikes INTEGER;
    v_block INTEGER;
BEGIN
    SELECT COALESCE(payroll_strikes, 0)
    INTO v_strikes
    FROM public.players
    WHERE discord_id = p_club_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    v_block := public.get_game_config_int('payroll_strike_market_block', 3)::INTEGER;
    IF v_strikes >= v_block THEN
        RAISE EXCEPTION
            'Payroll strikes block marketplace listing and scouting. Clear wage debt via Finances (strikes %).',
            v_strikes;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Payroll RPCs
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.process_club_weekly_payroll(
    p_club_id BIGINT,
    p_week_key TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_week TEXT := COALESCE(NULLIF(trim(p_week_key), ''), public.payroll_utc_week_key());
    v_player RECORD;
    v_existing RECORD;
    v_bill BIGINT;
    v_debt_before BIGINT;
    v_obligation BIGINT;
    v_paid BIGINT;
    v_debt_after BIGINT;
    v_strikes_after INTEGER;
    v_status TEXT;
    v_coins_after BIGINT;
BEGIN
    IF NOT public.wages_payroll_enabled() THEN
        RETURN jsonb_build_object(
            'status', 'skipped_flag',
            'week_key', v_week,
            'bill_coins', 0,
            'debt_before', 0,
            'paid_coins', 0,
            'debt_after', 0,
            'strikes_after', 0
        );
    END IF;

    SELECT *
    INTO v_player
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    IF COALESCE(v_player.is_ai, FALSE) THEN
        INSERT INTO public.payroll_runs (
            club_id, week_key, bill_coins, debt_before, paid_coins,
            debt_after, strikes_after, status
        ) VALUES (
            p_club_id, v_week, 0, 0, 0, 0, 0, 'skipped_ai'
        )
        ON CONFLICT (club_id, week_key) DO NOTHING;

        SELECT * INTO v_existing
        FROM public.payroll_runs
        WHERE club_id = p_club_id AND week_key = v_week;

        RETURN jsonb_build_object(
            'status', COALESCE(v_existing.status, 'skipped_ai'),
            'week_key', v_week,
            'bill_coins', 0,
            'debt_before', 0,
            'paid_coins', 0,
            'debt_after', 0,
            'strikes_after', 0,
            'coins_after', v_player.coins
        );
    END IF;

    SELECT * INTO v_existing
    FROM public.payroll_runs
    WHERE club_id = p_club_id AND week_key = v_week;

    IF FOUND THEN
        RETURN jsonb_build_object(
            'status', v_existing.status,
            'week_key', v_week,
            'bill_coins', v_existing.bill_coins,
            'debt_before', v_existing.debt_before,
            'paid_coins', v_existing.paid_coins,
            'debt_after', v_existing.debt_after,
            'strikes_after', v_existing.strikes_after,
            'coins_after', v_player.coins,
            'idempotent', true
        );
    END IF;

    v_bill := public.club_xi_weekly_wage_bill(p_club_id);
    v_debt_before := COALESCE(v_player.payroll_debt, 0);
    v_obligation := v_debt_before + v_bill;

    IF v_obligation = 0 THEN
        INSERT INTO public.payroll_runs (
            club_id, week_key, bill_coins, debt_before, paid_coins,
            debt_after, strikes_after, status
        ) VALUES (
            p_club_id, v_week, 0, 0, 0, 0, 0, 'skipped_zero'
        );

        UPDATE public.players
        SET last_payroll_at = NOW(),
            last_payroll_week = v_week,
            payroll_strikes = 0,
            payroll_debt = 0
        WHERE discord_id = p_club_id;

        RETURN jsonb_build_object(
            'status', 'skipped_zero',
            'week_key', v_week,
            'bill_coins', 0,
            'debt_before', 0,
            'paid_coins', 0,
            'debt_after', 0,
            'strikes_after', 0,
            'coins_after', v_player.coins
        );
    END IF;

    v_paid := LEAST(COALESCE(v_player.coins, 0), v_obligation);
    v_debt_after := v_obligation - v_paid;
    v_strikes_after := CASE
        WHEN v_debt_after > 0 THEN COALESCE(v_player.payroll_strikes, 0) + 1
        ELSE 0
    END;
    v_status := CASE WHEN v_debt_after > 0 THEN 'partial' ELSE 'paid' END;

    IF v_paid > 0 THEN
        PERFORM public.apply_club_economy(
            p_club_id,
            -v_paid,
            0,
            'weekly_payroll',
            'weekly_payroll:' || p_club_id::TEXT || ':' || v_week,
            jsonb_build_object(
                'week_key', v_week,
                'bill_coins', v_bill,
                'debt_before', v_debt_before,
                'paid_coins', v_paid
            )
        );
    END IF;

    UPDATE public.players
    SET payroll_debt = v_debt_after,
        payroll_strikes = v_strikes_after,
        last_payroll_at = NOW(),
        last_payroll_week = v_week
    WHERE discord_id = p_club_id;

    INSERT INTO public.payroll_runs (
        club_id, week_key, bill_coins, debt_before, paid_coins,
        debt_after, strikes_after, status
    ) VALUES (
        p_club_id, v_week, v_bill, v_debt_before, v_paid,
        v_debt_after, v_strikes_after, v_status
    );

    SELECT coins INTO v_coins_after FROM public.players WHERE discord_id = p_club_id;

    RETURN jsonb_build_object(
        'status', v_status,
        'week_key', v_week,
        'bill_coins', v_bill,
        'debt_before', v_debt_before,
        'paid_coins', v_paid,
        'debt_after', v_debt_after,
        'strikes_after', v_strikes_after,
        'coins_after', v_coins_after
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.process_weekly_payroll(
    p_week_key TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_week TEXT := COALESCE(NULLIF(trim(p_week_key), ''), public.payroll_utc_week_key());
    v_club RECORD;
    v_processed INTEGER := 0;
    v_skipped INTEGER := 0;
    v_result JSONB;
BEGIN
    IF NOT public.wages_payroll_enabled() THEN
        RETURN jsonb_build_object(
            'processed', 0,
            'skipped', 0,
            'week_key', v_week,
            'reason', 'flag_off'
        );
    END IF;

    FOR v_club IN
        SELECT p.discord_id, COALESCE(p.is_ai, FALSE) AS is_ai
        FROM public.players p
        WHERE NOT EXISTS (
            SELECT 1 FROM public.payroll_runs r
            WHERE r.club_id = p.discord_id AND r.week_key = v_week
        )
    LOOP
        v_result := public.process_club_weekly_payroll(v_club.discord_id, v_week);
        IF (v_result->>'status') IN ('skipped_ai', 'skipped_flag', 'skipped_zero') THEN
            v_skipped := v_skipped + 1;
        ELSE
            v_processed := v_processed + 1;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'processed', v_processed,
        'skipped', v_skipped,
        'week_key', v_week
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- T037: RPC-side strike market guards (patch live function bodies)
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    src TEXT;
BEGIN
    -- create_transfer_listing
    IF to_regprocedure('public.create_transfer_listing(bigint,uuid,bigint)') IS NOT NULL THEN
        src := pg_get_functiondef('public.create_transfer_listing(bigint,uuid,bigint)'::regprocedure);
        IF src NOT ILIKE '%assert_club_payroll_market_ok%' THEN
            src := replace(
                src,
                'PERFORM public.assert_not_in_match(p_seller_id);',
                E'PERFORM public.assert_not_in_match(p_seller_id);\n    PERFORM public.assert_club_payroll_market_ok(p_seller_id);'
            );
            EXECUTE src;
        END IF;
    END IF;

    -- purchase_scouting_player
    IF to_regprocedure('public.purchase_scouting_player(bigint,uuid,bigint)') IS NOT NULL THEN
        src := pg_get_functiondef('public.purchase_scouting_player(bigint,uuid,bigint)'::regprocedure);
        IF src NOT ILIKE '%assert_club_payroll_market_ok%' THEN
            src := replace(
                src,
                'PERFORM public.assert_not_in_match(p_buyer_id);',
                E'PERFORM public.assert_not_in_match(p_buyer_id);\n    PERFORM public.assert_club_payroll_market_ok(p_buyer_id);'
            );
            EXECUTE src;
        END IF;
    END IF;

    -- dispatch_youth_scout
    IF to_regprocedure('public.dispatch_youth_scout(bigint,text)') IS NOT NULL THEN
        src := pg_get_functiondef('public.dispatch_youth_scout(bigint,text)'::regprocedure);
        IF src NOT ILIKE '%assert_club_payroll_market_ok%' THEN
            IF position('RAISE EXCEPTION ''Manager not found'';' IN src) > 0 THEN
                src := replace(
                    src,
                    E'RAISE EXCEPTION ''Manager not found'';\n    END IF;',
                    E'RAISE EXCEPTION ''Manager not found'';\n    END IF;\n\n    PERFORM public.assert_club_payroll_market_ok(p_owner_id);'
                );
                EXECUTE src;
            END IF;
        END IF;
    END IF;

    -- sign_youth_scout_prospect
    IF to_regprocedure('public.sign_youth_scout_prospect(bigint,uuid,integer)') IS NOT NULL THEN
        src := pg_get_functiondef('public.sign_youth_scout_prospect(bigint,uuid,integer)'::regprocedure);
        IF src NOT ILIKE '%assert_club_payroll_market_ok%' THEN
            IF position('RAISE EXCEPTION ''Scout report not found'';' IN src) > 0 THEN
                src := replace(
                    src,
                    E'RAISE EXCEPTION ''Scout report not found'';\n    END IF;',
                    E'RAISE EXCEPTION ''Scout report not found'';\n    END IF;\n\n    PERFORM public.assert_club_payroll_market_ok(p_owner_id);'
                );
                EXECUTE src;
            END IF;
        END IF;
    END IF;
END $$;

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
            ('column:public.players.payroll_debt'),
            ('column:public.players.payroll_strikes'),
            ('column:public.players.last_payroll_at'),
            ('column:public.players.last_payroll_week'),
            ('table:public.payroll_runs'),
            ('function:wages_payroll_enabled'),
            ('function:payroll_utc_week_key'),
            ('function:card_weekly_wage_coins'),
            ('function:club_xi_weekly_wage_bill'),
            ('function:card_contract_blocks_xi'),
            ('function:assert_club_payroll_market_ok'),
            ('function:process_club_weekly_payroll'),
            ('function:process_weekly_payroll'),
            ('policy:public.payroll_runs.payroll_runs_select'),
            ('policy:public.payroll_runs.payroll_runs_insert'),
            ('policy:public.payroll_runs.payroll_runs_update')
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
        OR (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'wages_payroll_enabled'
                    THEN to_regprocedure('public.wages_payroll_enabled()')
                WHEN 'payroll_utc_week_key'
                    THEN to_regprocedure('public.payroll_utc_week_key(timestamptz)')
                WHEN 'card_weekly_wage_coins'
                    THEN to_regprocedure('public.card_weekly_wage_coins(integer,text)')
                WHEN 'club_xi_weekly_wage_bill'
                    THEN to_regprocedure('public.club_xi_weekly_wage_bill(bigint)')
                WHEN 'card_contract_blocks_xi'
                    THEN to_regprocedure('public.card_contract_blocks_xi(timestamptz)')
                WHEN 'assert_club_payroll_market_ok'
                    THEN to_regprocedure('public.assert_club_payroll_market_ok(bigint)')
                WHEN 'process_club_weekly_payroll'
                    THEN to_regprocedure('public.process_club_weekly_payroll(bigint,text)')
                WHEN 'process_weekly_payroll'
                    THEN to_regprocedure('public.process_weekly_payroll(text)')
                ELSE NULL
            END IS NOT NULL
        )
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1
                FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '063 schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

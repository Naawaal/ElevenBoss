-- 086: Marketplace intelligence — sale snapshots, ownership history, discovery, analytics
-- Spec: specs/043-marketplace-intelligence/ (US-42.6)

-- ---------------------------------------------------------------------------
-- Schema: enrich transfer_sales_log + ownership history
-- ---------------------------------------------------------------------------

ALTER TABLE public.transfer_sales_log
    ADD COLUMN IF NOT EXISTS fair_value_coins BIGINT,
    ADD COLUMN IF NOT EXISTS rarity TEXT,
    ADD COLUMN IF NOT EXISTS role TEXT,
    ADD COLUMN IF NOT EXISTS overall INTEGER,
    ADD COLUMN IF NOT EXISTS potential INTEGER,
    ADD COLUMN IF NOT EXISTS age_at_sale INTEGER,
    ADD COLUMN IF NOT EXISTS player_name TEXT;

CREATE INDEX IF NOT EXISTS transfer_sales_log_created_idx
    ON public.transfer_sales_log (created_at DESC);

CREATE INDEX IF NOT EXISTS transfer_sales_log_card_created_idx
    ON public.transfer_sales_log (card_id, created_at DESC);

CREATE INDEX IF NOT EXISTS transfer_sales_log_cohort_idx
    ON public.transfer_sales_log (role, rarity, overall, created_at DESC);

CREATE TABLE IF NOT EXISTS public.card_ownership_history (
    id BIGSERIAL PRIMARY KEY,
    card_id UUID NOT NULL,
    owner_id BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    club_name TEXT NOT NULL,
    acquired_via TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    ended_via TEXT,
    transfer_sales_log_id BIGINT REFERENCES public.transfer_sales_log(id) ON DELETE SET NULL,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS card_ownership_history_one_open_uidx
    ON public.card_ownership_history (card_id)
    WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS card_ownership_history_card_started_idx
    ON public.card_ownership_history (card_id, started_at ASC);

CREATE INDEX IF NOT EXISTS card_ownership_history_owner_idx
    ON public.card_ownership_history (owner_id, started_at DESC);

ALTER TABLE public.card_ownership_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS card_ownership_history_select ON public.card_ownership_history;
DROP POLICY IF EXISTS card_ownership_history_insert ON public.card_ownership_history;
DROP POLICY IF EXISTS card_ownership_history_update ON public.card_ownership_history;

CREATE POLICY card_ownership_history_select ON public.card_ownership_history
    FOR SELECT TO anon, authenticated, service_role USING (true);
CREATE POLICY card_ownership_history_insert ON public.card_ownership_history
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);
CREATE POLICY card_ownership_history_update ON public.card_ownership_history
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE public.card_ownership_history TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE public.card_ownership_history_id_seq TO anon, authenticated, service_role;

INSERT INTO public.game_config (key, value_json) VALUES
    ('price_discovery_min_sales', '5'),
    ('price_discovery_ovr_window', '3')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Ownership helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.ensure_card_ownership_open(
    p_card_id UUID,
    p_owner_id BIGINT,
    p_via TEXT DEFAULT 'legacy_bootstrap'
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_club TEXT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.card_ownership_history
        WHERE card_id = p_card_id AND ended_at IS NULL
    ) THEN
        RETURN;
    END IF;

    SELECT COALESCE(NULLIF(trim(club_name), ''), 'Unknown Club')
    INTO v_club
    FROM public.players
    WHERE discord_id = p_owner_id;

    INSERT INTO public.card_ownership_history (
        card_id, owner_id, club_name, acquired_via, started_at
    ) VALUES (
        p_card_id,
        p_owner_id,
        COALESCE(v_club, 'Unknown Club'),
        COALESCE(NULLIF(trim(p_via), ''), 'legacy_bootstrap'),
        NOW()
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_card_ownership_history(p_card_id UUID)
RETURNS JSONB
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'club_name', club_name,
                'owner_id', owner_id,
                'acquired_via', acquired_via,
                'started_at', started_at,
                'ended_at', ended_at,
                'ended_via', ended_via
            )
            ORDER BY started_at ASC
        ),
        '[]'::JSONB
    )
    FROM public.card_ownership_history
    WHERE card_id = p_card_id;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.ensure_card_ownership_open(UUID, BIGINT, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.get_card_ownership_history(UUID)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- purchase_transfer_listing — snapshots + ownership trail (extends 062)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.purchase_transfer_listing(
    p_buyer_id BIGINT,
    p_listing_id UUID,
    p_expected_price BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_listing public.transfer_listings%ROWTYPE;
    v_card_name TEXT;
    v_card_role TEXT;
    v_card_rarity TEXT;
    v_card_ovr INTEGER;
    v_card_pot INTEGER;
    v_card_dob DATE;
    v_card_age INTEGER;
    v_fair_value BIGINT;
    v_senior_roster_cap INTEGER;
    v_senior_roster_count INTEGER;
    v_tax_bps BIGINT;
    v_tax_amount BIGINT;
    v_seller_net BIGINT;
    v_sales_log_id BIGINT;
    v_buyer_club TEXT;
BEGIN
    IF NOT public.p2p_transfer_market_enabled() THEN
        RAISE EXCEPTION 'Transfer market is disabled';
    END IF;

    PERFORM public.assert_not_in_match(p_buyer_id);

    SELECT *
    INTO v_listing
    FROM public.transfer_listings
    WHERE id = p_listing_id
      AND status = 'active'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Listing not found or already sold';
    END IF;
    IF v_listing.expires_at <= NOW() THEN
        RAISE EXCEPTION 'Listing has expired';
    END IF;
    IF p_expected_price IS DISTINCT FROM v_listing.price_coins THEN
        RAISE EXCEPTION 'Price mismatch';
    END IF;
    IF p_buyer_id = v_listing.seller_id THEN
        RAISE EXCEPTION 'Cannot buy your own listing';
    END IF;

    PERFORM public.assert_not_in_match(v_listing.seller_id);

    PERFORM 1
    FROM public.players
    WHERE discord_id = p_buyer_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Buyer not found';
    END IF;

    SELECT COUNT(*)::INTEGER
    INTO v_senior_roster_count
    FROM public.player_cards
    WHERE owner_id = p_buyer_id
      AND COALESCE(in_academy, FALSE) = FALSE
      AND COALESCE(is_retired, FALSE) = FALSE;
    v_senior_roster_cap := public.get_game_config_int('senior_roster_cap', 48)::INTEGER;
    IF v_senior_roster_count >= v_senior_roster_cap THEN
        RAISE EXCEPTION 'Senior roster full';
    END IF;

    SELECT name, position, rarity, overall, potential, date_of_birth
    INTO v_card_name, v_card_role, v_card_rarity, v_card_ovr, v_card_pot, v_card_dob
    FROM public.player_cards
    WHERE id = v_listing.card_id
      AND owner_id = v_listing.seller_id
      AND COALESCE(is_retired, FALSE) = FALSE
      AND COALESCE(in_academy, FALSE) = FALSE
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Listing card is no longer available';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = v_listing.card_id
    ) THEN
        RAISE EXCEPTION 'Listing card is in a starting 11';
    END IF;

    v_card_age := public.card_age_from_dob(v_card_dob);
    v_fair_value := public.compute_agent_offer(v_card_ovr, v_card_rarity, v_card_age, v_card_pot);

    v_tax_bps := public.get_game_config_int('transfer_tax_bps', 1000);
    v_tax_amount := floor(v_listing.price_coins * v_tax_bps / 10000.0)::BIGINT;
    v_seller_net := v_listing.price_coins - v_tax_amount;

    PERFORM public.apply_club_economy(
        p_buyer_id,
        -v_listing.price_coins,
        0,
        'transfer_buy',
        'transfer_buy:' || p_listing_id::TEXT,
        jsonb_build_object(
            'listing_id', p_listing_id,
            'card_id', v_listing.card_id,
            'seller_id', v_listing.seller_id,
            'gross_price', v_listing.price_coins
        )
    );
    PERFORM public.apply_club_economy(
        v_listing.seller_id,
        v_seller_net,
        0,
        'transfer_sale',
        'transfer_sale:' || p_listing_id::TEXT,
        jsonb_build_object(
            'listing_id', p_listing_id,
            'card_id', v_listing.card_id,
            'buyer_id', p_buyer_id,
            'gross_price', v_listing.price_coins,
            'tax_amount', v_tax_amount
        )
    );

    DELETE FROM public.squad_assignments
    WHERE player_card_id = v_listing.card_id;

    UPDATE public.player_cards
    SET owner_id = p_buyer_id
    WHERE id = v_listing.card_id
      AND owner_id = v_listing.seller_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Listing card ownership changed';
    END IF;

    UPDATE public.transfer_listings
    SET status = 'sold',
        buyer_id = p_buyer_id,
        sold_at = NOW()
    WHERE id = p_listing_id;

    INSERT INTO public.transfer_sales_log (
        listing_id, seller_id, buyer_id, card_id,
        gross_price, tax_amount, seller_net,
        fair_value_coins, rarity, role, overall, potential, age_at_sale, player_name
    ) VALUES (
        p_listing_id, v_listing.seller_id, p_buyer_id, v_listing.card_id,
        v_listing.price_coins, v_tax_amount, v_seller_net,
        v_fair_value, v_card_rarity, v_card_role, v_card_ovr, v_card_pot, v_card_age, v_card_name
    )
    RETURNING id INTO v_sales_log_id;

    -- Close seller open segment (no-op if none); open buyer segment.
    UPDATE public.card_ownership_history
    SET ended_at = NOW(),
        ended_via = 'p2p_transfer',
        transfer_sales_log_id = v_sales_log_id
    WHERE card_id = v_listing.card_id
      AND ended_at IS NULL;

    SELECT COALESCE(NULLIF(trim(club_name), ''), 'Unknown Club')
    INTO v_buyer_club
    FROM public.players
    WHERE discord_id = p_buyer_id;

    INSERT INTO public.card_ownership_history (
        card_id, owner_id, club_name, acquired_via, started_at, transfer_sales_log_id
    ) VALUES (
        v_listing.card_id,
        p_buyer_id,
        COALESCE(v_buyer_club, 'Unknown Club'),
        'p2p_transfer',
        NOW(),
        v_sales_log_id
    );

    RETURN jsonb_build_object(
        'listing_id', p_listing_id,
        'card_id', v_listing.card_id,
        'player_name', v_card_name,
        'gross_price', v_listing.price_coins,
        'tax_amount', v_tax_amount,
        'seller_net', v_seller_net,
        'seller_id', v_listing.seller_id,
        'buyer_id', p_buyer_id,
        'fair_value_coins', v_fair_value
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- process_agent_sale — close ownership before DELETE (from 075 body)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ovr INTEGER;
    v_rarity TEXT;
    v_potential INTEGER;
    v_dob DATE;
    v_age INTEGER;
    v_retired BOOLEAN;
    v_injury_tier INTEGER;
    v_in_hospital BOOLEAN;
    v_sale_value BIGINT;
    v_sale_count INTEGER;
    v_cap INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.assert_card_action_allowed(p_club_id, p_card_id, 'agent_sell');

    v_cap := public.get_game_config_int('agent_sale_daily_cap', 10)::INTEGER;

    INSERT INTO public.agent_sale_daily_log (club_id, sale_date, count)
    VALUES (p_club_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, sale_date)
    DO UPDATE SET count = agent_sale_daily_log.count + 1
    RETURNING count INTO v_sale_count;

    IF v_sale_count > v_cap THEN
        RAISE EXCEPTION 'Daily agent sale limit reached (max % per day)', v_cap;
    END IF;

    SELECT
        overall, rarity, potential, date_of_birth, COALESCE(is_retired, FALSE),
        injury_tier, COALESCE(in_hospital, FALSE)
    INTO
        v_ovr, v_rarity, v_potential, v_dob, v_retired,
        v_injury_tier, v_in_hospital
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_club_id
    FOR UPDATE;

    IF v_ovr IS NULL THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;
    IF v_retired THEN
        RAISE EXCEPTION 'Cannot sell a retired player';
    END IF;
    IF v_injury_tier IS NOT NULL OR v_in_hospital THEN
        RAISE EXCEPTION 'Cannot sell an injured player';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_card_id
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in your starting 11';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in active training';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot sell a player in an active evolution';
    END IF;

    v_age := public.card_age_from_dob(v_dob);
    v_sale_value := public.compute_agent_offer(v_ovr, v_rarity, v_age, v_potential);

    UPDATE public.card_ownership_history
    SET ended_at = NOW(),
        ended_via = 'agent_sale'
    WHERE card_id = p_card_id
      AND ended_at IS NULL;

    DELETE FROM public.player_cards WHERE id = p_card_id;

    PERFORM public.apply_club_economy(
        p_club_id, v_sale_value, 0, 'agent_sale',
        'agent_sale:' || p_card_id::TEXT,
        jsonb_build_object(
            'card_id', p_card_id, 'ovr', v_ovr, 'rarity', v_rarity,
            'age', v_age, 'potential', v_potential
        )
    );

    RETURN v_sale_value;
END;
$$;

-- ---------------------------------------------------------------------------
-- Optional acquisition opens (scouting / youth)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.purchase_scouting_player(
    p_buyer_id BIGINT,
    p_pool_id UUID,
    p_expected_price BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_row RECORD;
    v_card_id UUID;
BEGIN
    PERFORM public.assert_not_in_match(p_buyer_id);

    SELECT * INTO v_row
    FROM public.scouting_pool_players
    WHERE id = p_pool_id AND claimed_by IS NULL
    FOR UPDATE;

    IF v_row IS NULL THEN
        RAISE EXCEPTION 'Scouting listing not found or already signed';
    END IF;

    IF p_expected_price IS DISTINCT FROM v_row.list_price THEN
        RAISE EXCEPTION 'Price mismatch (expected % coins)', v_row.list_price;
    END IF;

    PERFORM public.apply_club_economy(
        p_buyer_id,
        -v_row.list_price,
        0,
        'scouting_signing',
        'scouting:' || p_pool_id::TEXT,
        jsonb_build_object('pool_id', p_pool_id, 'price', v_row.list_price)
    );

    INSERT INTO public.player_cards (
        owner_id, name, position, rarity, base_rating, level, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
    ) VALUES (
        p_buyer_id, v_row.name, v_row.position, v_row.rarity,
        v_row.base_rating, 1, v_row.overall,
        v_row.pac, v_row.sho, v_row.pas, v_row.dri, v_row.def, v_row.phy,
        v_row.potential, v_row.base_potential, v_row.age, v_row.date_of_birth,
        COALESCE(NULLIF(trim(v_row.role), ''), 'Balanced')
    ) RETURNING id INTO v_card_id;

    UPDATE public.scouting_pool_players
    SET claimed_by = p_buyer_id, claimed_at = NOW()
    WHERE id = p_pool_id;

    PERFORM public.ensure_card_ownership_open(v_card_id, p_buyer_id, 'scouting');

    RETURN jsonb_build_object(
        'pool_id', p_pool_id,
        'card_id', v_card_id,
        'coins_spent', v_row.list_price,
        'player_name', v_row.name
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.sign_youth_scout_prospect(
    p_owner_id BIGINT,
    p_report_id UUID,
    p_index INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_report RECORD;
    v_card JSONB;
    v_level INTEGER;
    v_cap INTEGER;
    v_used INTEGER;
    v_dob DATE;
    v_pot INT;
    v_card_id UUID;
BEGIN
    SELECT * INTO v_report
    FROM public.scouting_reports
    WHERE id = p_report_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Scout report not found';
    END IF;
    IF v_report.signed_card_id IS NOT NULL THEN
        RAISE EXCEPTION 'Report already signed';
    END IF;
    IF v_report.expires_at <= NOW() THEN
        RAISE EXCEPTION 'Report expired';
    END IF;
    IF p_index < 0 OR p_index > 2 THEN
        RAISE EXCEPTION 'Invalid prospect index';
    END IF;

    SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
    v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.player_cards
    WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
    IF COALESCE(v_used, 0) >= v_cap THEN
        RAISE EXCEPTION 'Academy slots full';
    END IF;

    v_card := v_report.prospects_json -> p_index;
    IF v_card IS NULL OR jsonb_typeof(v_card) <> 'object' THEN
        RAISE EXCEPTION 'Prospect missing';
    END IF;

    v_pot := COALESCE((v_card->>'potential')::INT, (v_card->>'base_potential')::INT);
    IF v_pot IS NULL THEN
        RAISE EXCEPTION 'Prospect missing potential';
    END IF;
    IF v_pot < COALESCE((v_card->>'overall')::INT, 0) THEN
        v_pot := (v_card->>'overall')::INT;
    END IF;

    v_dob := COALESCE(
        NULLIF(v_card->>'date_of_birth', '')::DATE,
        (CURRENT_DATE - (COALESCE((v_card->>'age')::INT, 18) || ' years')::INTERVAL)::DATE
    );

    INSERT INTO public.player_cards (
        owner_id, name, position, rarity, base_rating, level, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
        in_academy, academy_progress, academy_seated_at
    ) VALUES (
        p_owner_id,
        v_card->>'name',
        v_card->>'position',
        COALESCE(v_card->>'rarity', 'Common'),
        COALESCE((v_card->>'base_rating')::INT, (v_card->>'overall')::INT),
        1,
        (v_card->>'overall')::INT,
        COALESCE((v_card->>'pac')::INT, 50),
        COALESCE((v_card->>'sho')::INT, 50),
        COALESCE((v_card->>'pas')::INT, 50),
        COALESCE((v_card->>'dri')::INT, 50),
        COALESCE((v_card->>'def')::INT, 50),
        COALESCE((v_card->>'phy')::INT, 50),
        v_pot,
        COALESCE((v_card->>'base_potential')::INT, v_pot),
        public.card_age_from_dob(v_dob),
        v_dob,
        COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced'),
        TRUE, 0, NOW()
    ) RETURNING id INTO v_card_id;

    UPDATE public.scouting_reports
    SET signed_card_id = v_card_id
    WHERE id = p_report_id;

    PERFORM public.ensure_card_ownership_open(v_card_id, p_owner_id, 'youth_scout');

    RETURN jsonb_build_object(
        'card_id', v_card_id,
        'report_id', p_report_id,
        'index', p_index
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Price discovery
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_price_discovery(
    p_role TEXT,
    p_rarity TEXT,
    p_overall INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_min INTEGER := public.get_game_config_int('price_discovery_min_sales', 5)::INTEGER;
    v_window INTEGER := public.get_game_config_int('price_discovery_ovr_window', 3)::INTEGER;
    v_sample INTEGER := 0;
    v_avg NUMERIC;
    v_median NUMERIC;
    v_recent JSONB;
    v_trend TEXT;
    v_med_recent NUMERIC;
    v_med_prior NUMERIC;
    v_active_count INTEGER := 0;
    v_lowest BIGINT;
    v_highest BIGINT;
BEGIN
    SELECT COUNT(*)::INTEGER,
           AVG(gross_price)::NUMERIC,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gross_price)::NUMERIC
    INTO v_sample, v_avg, v_median
    FROM public.transfer_sales_log
    WHERE role IS NOT NULL
      AND rarity IS NOT NULL
      AND overall IS NOT NULL
      AND role = p_role
      AND rarity = p_rarity
      AND overall BETWEEN (p_overall - v_window) AND (p_overall + v_window);

    SELECT COALESCE(jsonb_agg(row_to_json(r)::JSONB), '[]'::JSONB)
    INTO v_recent
    FROM (
        SELECT gross_price, created_at, overall
        FROM public.transfer_sales_log
        WHERE role IS NOT NULL
          AND rarity IS NOT NULL
          AND overall IS NOT NULL
          AND role = p_role
          AND rarity = p_rarity
          AND overall BETWEEN (p_overall - v_window) AND (p_overall + v_window)
        ORDER BY created_at DESC
        LIMIT 5
    ) r;

    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gross_price)::NUMERIC
    INTO v_med_recent
    FROM public.transfer_sales_log
    WHERE role = p_role AND rarity = p_rarity
      AND overall BETWEEN (p_overall - v_window) AND (p_overall + v_window)
      AND role IS NOT NULL AND rarity IS NOT NULL AND overall IS NOT NULL
      AND created_at >= NOW() - INTERVAL '7 days';

    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gross_price)::NUMERIC
    INTO v_med_prior
    FROM public.transfer_sales_log
    WHERE role = p_role AND rarity = p_rarity
      AND overall BETWEEN (p_overall - v_window) AND (p_overall + v_window)
      AND role IS NOT NULL AND rarity IS NOT NULL AND overall IS NOT NULL
      AND created_at >= NOW() - INTERVAL '14 days'
      AND created_at < NOW() - INTERVAL '7 days';

    IF v_med_recent IS NULL OR v_med_prior IS NULL THEN
        v_trend := NULL;
    ELSIF v_med_recent > v_med_prior THEN
        v_trend := 'up';
    ELSIF v_med_recent < v_med_prior THEN
        v_trend := 'down';
    ELSE
        v_trend := 'flat';
    END IF;

    SELECT COUNT(*)::INTEGER, MIN(tl.price_coins), MAX(tl.price_coins)
    INTO v_active_count, v_lowest, v_highest
    FROM public.transfer_listings tl
    JOIN public.player_cards pc ON pc.id = tl.card_id
    WHERE tl.status = 'active'
      AND tl.expires_at > NOW()
      AND pc.position = p_role
      AND pc.rarity = p_rarity
      AND pc.overall BETWEEN (p_overall - v_window) AND (p_overall + v_window);

    IF v_sample < v_min THEN
        RETURN jsonb_build_object(
            'role', p_role,
            'rarity', p_rarity,
            'overall', p_overall,
            'ovr_window', v_window,
            'min_sales', v_min,
            'sample_size', v_sample,
            'insufficient_data', true,
            'recent_sales', v_recent,
            'trend', NULL,
            'active_count', v_active_count,
            'lowest_active', v_lowest,
            'highest_active', v_highest
        );
    END IF;

    RETURN jsonb_build_object(
        'role', p_role,
        'rarity', p_rarity,
        'overall', p_overall,
        'ovr_window', v_window,
        'min_sales', v_min,
        'sample_size', v_sample,
        'insufficient_data', false,
        'avg_sale_price', round(v_avg)::BIGINT,
        'median_sale_price', round(v_median)::BIGINT,
        'recent_sales', v_recent,
        'trend', v_trend,
        'active_count', v_active_count,
        'lowest_active', v_lowest,
        'highest_active', v_highest
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.get_price_discovery(TEXT, TEXT, INTEGER)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Market analytics (ops)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_market_analytics(
    p_from TIMESTAMPTZ,
    p_to TIMESTAMPTZ
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_sales_count INTEGER;
    v_gross BIGINT;
    v_tax BIGINT;
    v_avg_hours NUMERIC;
    v_created INTEGER;
    v_expired INTEGER;
    v_cancelled INTEGER;
    v_sold INTEGER;
    v_agent_count INTEGER;
    v_agent_coins BIGINT;
    v_top_pos JSONB;
    v_top_rar JSONB;
    v_highest JSONB;
    v_active_clubs JSONB;
    v_daily JSONB;
    v_success NUMERIC;
BEGIN
    SELECT COUNT(*)::INTEGER,
           COALESCE(SUM(gross_price), 0)::BIGINT,
           COALESCE(SUM(tax_amount), 0)::BIGINT
    INTO v_sales_count, v_gross, v_tax
    FROM public.transfer_sales_log
    WHERE created_at >= p_from AND created_at < p_to;

    SELECT AVG(EXTRACT(EPOCH FROM (tl.sold_at - tl.created_at)) / 3600.0)
    INTO v_avg_hours
    FROM public.transfer_listings tl
    WHERE tl.status = 'sold'
      AND tl.sold_at >= p_from AND tl.sold_at < p_to
      AND tl.sold_at IS NOT NULL;

    SELECT COUNT(*)::INTEGER INTO v_created
    FROM public.transfer_listings
    WHERE created_at >= p_from AND created_at < p_to;

    SELECT COUNT(*)::INTEGER INTO v_expired
    FROM public.transfer_listings
    WHERE status = 'expired'
      AND COALESCE(cancelled_at, expires_at) >= p_from
      AND COALESCE(cancelled_at, expires_at) < p_to;

    SELECT COUNT(*)::INTEGER INTO v_cancelled
    FROM public.transfer_listings
    WHERE status = 'cancelled'
      AND cancelled_at >= p_from AND cancelled_at < p_to;

    SELECT COUNT(*)::INTEGER INTO v_sold
    FROM public.transfer_listings
    WHERE status = 'sold'
      AND sold_at >= p_from AND sold_at < p_to;

    IF v_created > 0 THEN
        v_success := round((v_sold::NUMERIC / v_created::NUMERIC), 4);
    ELSE
        v_success := NULL;
    END IF;

    SELECT COUNT(*)::INTEGER, COALESCE(SUM(amount), 0)::BIGINT
    INTO v_agent_count, v_agent_coins
    FROM public.economy_ledger
    WHERE source = 'agent_sale'
      AND created_at >= p_from AND created_at < p_to
      AND amount > 0;

    SELECT COALESCE(jsonb_agg(jsonb_build_object('role', role, 'count', cnt) ORDER BY cnt DESC), '[]'::JSONB)
    INTO v_top_pos
    FROM (
        SELECT role, COUNT(*)::INTEGER AS cnt
        FROM public.transfer_sales_log
        WHERE created_at >= p_from AND created_at < p_to AND role IS NOT NULL
        GROUP BY role
        ORDER BY cnt DESC
        LIMIT 5
    ) t;

    SELECT COALESCE(jsonb_agg(jsonb_build_object('rarity', rarity, 'count', cnt) ORDER BY cnt DESC), '[]'::JSONB)
    INTO v_top_rar
    FROM (
        SELECT rarity, COUNT(*)::INTEGER AS cnt
        FROM public.transfer_sales_log
        WHERE created_at >= p_from AND created_at < p_to AND rarity IS NOT NULL
        GROUP BY rarity
        ORDER BY cnt DESC
        LIMIT 5
    ) t;

    SELECT COALESCE(jsonb_agg(row_to_json(h)::JSONB), '[]'::JSONB)
    INTO v_highest
    FROM (
        SELECT gross_price, player_name, role, rarity, overall, created_at, seller_id, buyer_id
        FROM public.transfer_sales_log
        WHERE created_at >= p_from AND created_at < p_to
        ORDER BY gross_price DESC
        LIMIT 5
    ) h;

    SELECT COALESCE(jsonb_agg(jsonb_build_object('club_id', club_id, 'activity', activity) ORDER BY activity DESC), '[]'::JSONB)
    INTO v_active_clubs
    FROM (
        SELECT club_id, SUM(n)::INTEGER AS activity
        FROM (
            SELECT seller_id AS club_id, COUNT(*)::INTEGER AS n
            FROM public.transfer_sales_log
            WHERE created_at >= p_from AND created_at < p_to
            GROUP BY seller_id
            UNION ALL
            SELECT buyer_id AS club_id, COUNT(*)::INTEGER AS n
            FROM public.transfer_sales_log
            WHERE created_at >= p_from AND created_at < p_to
            GROUP BY buyer_id
        ) u
        GROUP BY club_id
        ORDER BY activity DESC
        LIMIT 10
    ) a;

    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'day', day,
        'sales_count', sales_count,
        'gross', gross,
        'tax', tax
    ) ORDER BY day), '[]'::JSONB)
    INTO v_daily
    FROM (
        SELECT (created_at AT TIME ZONE 'UTC')::DATE AS day,
               COUNT(*)::INTEGER AS sales_count,
               COALESCE(SUM(gross_price), 0)::BIGINT AS gross,
               COALESCE(SUM(tax_amount), 0)::BIGINT AS tax
        FROM public.transfer_sales_log
        WHERE created_at >= p_from AND created_at < p_to
        GROUP BY 1
        ORDER BY 1
    ) d;

    RETURN jsonb_build_object(
        'from', p_from,
        'to', p_to,
        'p2p_sales_count', v_sales_count,
        'p2p_gross_volume', v_gross,
        'tax_removed', v_tax,
        'avg_hours_to_sale', v_avg_hours,
        'listings_created', v_created,
        'listings_expired', v_expired,
        'listings_cancelled', v_cancelled,
        'listings_sold', v_sold,
        'listing_success_rate', v_success,
        'agent_sale_count', v_agent_count,
        'agent_coins_paid', v_agent_coins,
        'top_positions', v_top_pos,
        'top_rarities', v_top_rar,
        'highest_transfers', v_highest,
        'most_active_clubs', v_active_clubs,
        'daily_volume', v_daily
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.get_market_analytics(TIMESTAMPTZ, TIMESTAMPTZ)
    TO anon, authenticated, service_role;

GRANT ALL PRIVILEGES ON FUNCTION public.purchase_transfer_listing(BIGINT, UUID, BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale(BIGINT, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.purchase_scouting_player(BIGINT, UUID, BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.sign_youth_scout_prospect(BIGINT, UUID, INTEGER)
    TO anon, authenticated, service_role;

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
            ('table:public.card_ownership_history'),
            ('column:public.transfer_sales_log.fair_value_coins'),
            ('column:public.transfer_sales_log.rarity'),
            ('column:public.transfer_sales_log.role'),
            ('function:ensure_card_ownership_open'),
            ('function:get_card_ownership_history'),
            ('function:get_price_discovery'),
            ('function:get_market_analytics'),
            ('policy:public.card_ownership_history.card_ownership_history_select')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'column:%'
            AND EXISTS (
                SELECT 1 FROM information_schema.columns c
                WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'ensure_card_ownership_open'
                    THEN to_regprocedure('public.ensure_card_ownership_open(uuid,bigint,text)')
                WHEN 'get_card_ownership_history'
                    THEN to_regprocedure('public.get_card_ownership_history(uuid)')
                WHEN 'get_price_discovery'
                    THEN to_regprocedure('public.get_price_discovery(text,text,integer)')
                WHEN 'get_market_analytics'
                    THEN to_regprocedure('public.get_market_analytics(timestamptz,timestamptz)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '086 marketplace intelligence guard failed — missing: %', v_missing;
    END IF;
END;
$$;

-- 062: Player-to-player transfer market
-- Spec: specs/017-player-transfer-market/

-- ---------------------------------------------------------------------------
-- Schema and configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.transfer_listings (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id    BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    card_id      UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    price_coins  BIGINT NOT NULL CHECK (price_coins > 0),
    status       TEXT NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'sold', 'cancelled', 'expired')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL,
    sold_at      TIMESTAMPTZ,
    buyer_id     BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    cancelled_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS transfer_listings_one_active_card_uidx
    ON public.transfer_listings (card_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS transfer_listings_status_expires_idx
    ON public.transfer_listings (status, expires_at);

CREATE INDEX IF NOT EXISTS transfer_listings_seller_status_idx
    ON public.transfer_listings (seller_id, status);

CREATE TABLE IF NOT EXISTS public.transfer_sales_log (
    id          BIGSERIAL PRIMARY KEY,
    listing_id  UUID NOT NULL REFERENCES public.transfer_listings(id) ON DELETE RESTRICT,
    seller_id   BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE RESTRICT,
    buyer_id    BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE RESTRICT,
    card_id     UUID NOT NULL,
    gross_price BIGINT NOT NULL CHECK (gross_price > 0),
    tax_amount  BIGINT NOT NULL CHECK (tax_amount >= 0),
    seller_net  BIGINT NOT NULL CHECK (seller_net >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (gross_price = tax_amount + seller_net),
    UNIQUE (listing_id)
);

CREATE INDEX IF NOT EXISTS transfer_sales_log_buyer_card_created_idx
    ON public.transfer_sales_log (buyer_id, card_id, created_at DESC);

INSERT INTO public.game_config (key, value_json) VALUES
    ('p2p_transfer_market_enabled', 'false'),
    ('transfer_listing_slot_cap', '5'),
    ('transfer_tax_bps', '1000'),
    ('transfer_price_floor_mult', '0.75'),
    ('transfer_price_ceil_mult', '2.5'),
    ('transfer_listing_ttl_hours', '72'),
    ('transfer_relist_cooldown_hours', '6')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Listing helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.p2p_transfer_market_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('p2p_transfer_market_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

CREATE OR REPLACE FUNCTION public.card_is_on_transfer_list(p_card_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.transfer_listings
        WHERE card_id = p_card_id
          AND status = 'active'
    );
$$;

REVOKE ALL ON FUNCTION public.card_is_on_transfer_list(UUID) FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.assert_card_not_on_transfer_list(p_card_id UUID)
RETURNS VOID
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF public.card_is_on_transfer_list(p_card_id) THEN
        RAISE EXCEPTION 'Player is currently listed on the transfer market';
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Transfer listing lifecycle
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.create_transfer_listing(
    p_seller_id BIGINT,
    p_card_id UUID,
    p_price BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_slot_cap INTEGER;
    v_active_count INTEGER;
    v_ttl_hours INTEGER;
    v_cooldown_hours INTEGER;
    v_floor_mult NUMERIC;
    v_ceil_mult NUMERIC;
    v_fair_value BIGINT;
    v_price_floor BIGINT;
    v_price_ceil BIGINT;
    v_tax_bps BIGINT;
    v_listing_id UUID;
    v_expires_at TIMESTAMPTZ;
BEGIN
    IF NOT public.p2p_transfer_market_enabled() THEN
        RAISE EXCEPTION 'Transfer market is disabled';
    END IF;

    PERFORM public.assert_not_in_match(p_seller_id);

    -- Serialize per-club slot checks across concurrent listing attempts.
    PERFORM 1
    FROM public.players
    WHERE discord_id = p_seller_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Seller not found';
    END IF;

    SELECT *
    INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id
      AND owner_id = p_seller_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;
    IF COALESCE(v_card.is_retired, FALSE) THEN
        RAISE EXCEPTION 'Cannot list a retired player';
    END IF;
    IF COALESCE(v_card.in_academy, FALSE) THEN
        RAISE EXCEPTION 'Cannot list a player in the academy';
    END IF;
    IF v_card.injury_tier IS NOT NULL OR COALESCE(v_card.in_hospital, FALSE) THEN
        RAISE EXCEPTION 'Cannot list an injured player';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    ) THEN
        RAISE EXCEPTION 'Cannot list a player in your starting 11';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    ) THEN
        RAISE EXCEPTION 'Cannot list a player in active training';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot list a player in an active evolution';
    END IF;

    PERFORM public.assert_card_not_on_transfer_list(p_card_id);

    v_slot_cap := public.get_game_config_int('transfer_listing_slot_cap', 5)::INTEGER;
    SELECT COUNT(*)::INTEGER
    INTO v_active_count
    FROM public.transfer_listings
    WHERE seller_id = p_seller_id AND status = 'active';
    IF v_active_count >= v_slot_cap THEN
        RAISE EXCEPTION 'Listing slots full (max % active listings)', v_slot_cap;
    END IF;

    v_cooldown_hours :=
        public.get_game_config_int('transfer_relist_cooldown_hours', 6)::INTEGER;
    IF EXISTS (
        SELECT 1
        FROM public.transfer_sales_log
        WHERE buyer_id = p_seller_id
          AND card_id = p_card_id
          AND created_at > NOW() - make_interval(hours => v_cooldown_hours)
    ) THEN
        RAISE EXCEPTION
            'Card recently acquired via transfer; wait % hours before relisting',
            v_cooldown_hours;
    END IF;

    v_floor_mult := COALESCE(
        (public.get_game_config('transfer_price_floor_mult') #>> '{}')::NUMERIC,
        0.75
    );
    v_ceil_mult := COALESCE(
        (public.get_game_config('transfer_price_ceil_mult') #>> '{}')::NUMERIC,
        2.5
    );
    v_fair_value := public.compute_agent_offer(
        v_card.overall,
        v_card.rarity,
        public.card_age_from_dob(v_card.date_of_birth),
        v_card.potential
    );
    v_price_floor := GREATEST(50, floor(v_fair_value * v_floor_mult)::BIGINT);
    v_price_ceil := GREATEST(
        v_price_floor,
        floor(v_fair_value * v_ceil_mult)::BIGINT
    );
    IF p_price IS NULL OR p_price < v_price_floor OR p_price > v_price_ceil THEN
        RAISE EXCEPTION 'Price must be between % and %', v_price_floor, v_price_ceil;
    END IF;

    v_ttl_hours := public.get_game_config_int('transfer_listing_ttl_hours', 72)::INTEGER;
    v_expires_at := NOW() + make_interval(hours => v_ttl_hours);
    INSERT INTO public.transfer_listings (
        seller_id, card_id, price_coins, status, expires_at
    ) VALUES (
        p_seller_id, p_card_id, p_price, 'active', v_expires_at
    ) RETURNING id INTO v_listing_id;

    v_tax_bps := public.get_game_config_int('transfer_tax_bps', 1000);
    RETURN jsonb_build_object(
        'listing_id', v_listing_id,
        'card_id', p_card_id,
        'price_coins', p_price,
        'seller_net_if_sold', p_price - floor(p_price * v_tax_bps / 10000.0)::BIGINT,
        'expires_at', v_expires_at,
        'active_listings', v_active_count + 1,
        'slot_cap', v_slot_cap
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.cancel_transfer_listing(
    p_seller_id BIGINT,
    p_listing_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_listing public.transfer_listings%ROWTYPE;
BEGIN
    SELECT *
    INTO v_listing
    FROM public.transfer_listings
    WHERE id = p_listing_id
      AND seller_id = p_seller_id
      AND status = 'active'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active listing not found or not owned';
    END IF;

    UPDATE public.transfer_listings
    SET status = 'cancelled',
        cancelled_at = NOW()
    WHERE id = p_listing_id;

    RETURN jsonb_build_object(
        'listing_id', p_listing_id,
        'card_id', v_listing.card_id,
        'status', 'cancelled'
    );
END;
$$;

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
    v_senior_roster_cap INTEGER;
    v_senior_roster_count INTEGER;
    v_tax_bps BIGINT;
    v_tax_amount BIGINT;
    v_seller_net BIGINT;
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

    -- Serialize senior-roster capacity checks across concurrent purchases.
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

    SELECT name
    INTO v_card_name
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
        gross_price, tax_amount, seller_net
    ) VALUES (
        p_listing_id, v_listing.seller_id, p_buyer_id, v_listing.card_id,
        v_listing.price_coins, v_tax_amount, v_seller_net
    );

    RETURN jsonb_build_object(
        'listing_id', p_listing_id,
        'card_id', v_listing.card_id,
        'player_name', v_card_name,
        'gross_price', v_listing.price_coins,
        'tax_amount', v_tax_amount,
        'seller_net', v_seller_net,
        'seller_id', v_listing.seller_id,
        'buyer_id', p_buyer_id
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.expire_stale_transfer_listings()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_expired_count INTEGER;
BEGIN
    UPDATE public.transfer_listings
    SET status = 'expired',
        cancelled_at = NOW()
    WHERE status = 'active'
      AND expires_at <= NOW();

    GET DIAGNOSTICS v_expired_count = ROW_COUNT;
    RETURN jsonb_build_object('expired_count', v_expired_count);
END;
$$;

-- ---------------------------------------------------------------------------
-- Existing mutation paths blocked while a card is actively listed.
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

CREATE OR REPLACE FUNCTION public.set_formation_and_assignments(
    p_discord_id BIGINT,
    p_formation TEXT,
    p_assignments JSONB
) RETURNS BOOLEAN AS $$
DECLARE
    v_row JSONB;
    v_slot INTEGER;
    v_card_id UUID;
    v_pos TEXT;
    v_count INTEGER := 0;
BEGIN
    PERFORM public.assert_not_in_match(p_discord_id);

    IF p_formation NOT IN ('4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '5-3-2') THEN
        RAISE EXCEPTION 'Invalid formation';
    END IF;

    FOR v_row IN SELECT * FROM jsonb_array_elements(p_assignments)
    LOOP
        v_slot := (v_row->>'slot')::INTEGER;
        v_card_id := (v_row->>'card_id')::UUID;
        PERFORM public.assert_card_not_on_transfer_list(v_card_id);
        SELECT position INTO v_pos
        FROM public.player_cards
        WHERE id = v_card_id AND owner_id = p_discord_id;
        IF v_pos IS NULL THEN
            RAISE EXCEPTION 'Assignment includes unowned or missing card';
        END IF;
        IF v_slot = 1 AND v_pos != 'GK' THEN
            RAISE EXCEPTION 'Slot 1 requires a goalkeeper';
        END IF;
        v_count := v_count + 1;
    END LOOP;

    UPDATE public.squads
    SET formation = p_formation, updated_at = NOW()
    WHERE discord_id = p_discord_id;

    DELETE FROM public.squad_assignments WHERE discord_id = p_discord_id;

    FOR v_row IN SELECT * FROM jsonb_array_elements(p_assignments)
    LOOP
        INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
        VALUES (
            p_discord_id,
            (v_row->>'slot')::INTEGER,
            (v_row->>'card_id')::UUID
        );
    END LOOP;

    IF v_count = 11 THEN
        UPDATE public.players
        SET squad_invalid = FALSE
        WHERE discord_id = p_discord_id;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.swap_squad_players(
    p_discord_id BIGINT,
    p_slot INTEGER,
    p_reserve_card_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_starter_id UUID;
    v_reserve_pos TEXT;
    v_formation TEXT;
    v_required_role TEXT;
BEGIN
    PERFORM public.assert_not_in_match(p_discord_id);
    PERFORM public.assert_card_not_on_transfer_list(p_reserve_card_id);

    IF p_slot < 1 OR p_slot > 11 THEN
        RAISE EXCEPTION 'Invalid squad slot';
    END IF;

    SELECT position INTO v_reserve_pos
    FROM public.player_cards
    WHERE id = p_reserve_card_id AND owner_id = p_discord_id
    FOR UPDATE;

    IF v_reserve_pos IS NULL THEN
        RAISE EXCEPTION 'Reserve player not found or not owned';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE discord_id = p_discord_id AND player_card_id = p_reserve_card_id
    ) THEN
        RAISE EXCEPTION 'Reserve player is already in the starting 11';
    END IF;

    SELECT formation INTO v_formation
    FROM public.squads
    WHERE discord_id = p_discord_id;
    v_required_role := public.formation_slot_role(
        COALESCE(v_formation, '4-4-2'), p_slot
    );
    IF v_reserve_pos != v_required_role THEN
        RAISE EXCEPTION
            'Player position % does not match slot requirement %',
            v_reserve_pos, v_required_role;
    END IF;

    SELECT player_card_id INTO v_starter_id
    FROM public.squad_assignments
    WHERE discord_id = p_discord_id AND position_slot = p_slot
    FOR UPDATE;
    IF v_starter_id IS NULL THEN
        RAISE EXCEPTION 'No starter assigned to that slot';
    END IF;

    DELETE FROM public.squad_assignments
    WHERE discord_id = p_discord_id AND position_slot = p_slot;
    INSERT INTO public.squad_assignments (discord_id, position_slot, player_card_id)
    VALUES (p_discord_id, p_slot, p_reserve_card_id);

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- T011 peer guards — progression/recovery RPCs block listed cards
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
    v_reset DATE;
    v_tg_level INTEGER;
    v_ovr INTEGER;
    v_card_level INTEGER;
    v_dob DATE;
    v_age INTEGER;
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

    SELECT coins, action_energy, daily_drill_count, daily_drill_reset_at,
           COALESCE(training_ground_level, 1)
    INTO v_coins, v_energy, v_daily, v_reset, v_tg_level
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);

    -- Null-safe soft-reset (parity with process_recovery_session)
    IF v_reset IS NULL OR v_reset < CURRENT_DATE THEN
        v_daily := 0;
        v_reset := CURRENT_DATE;
    END IF;

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
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_owner_id AND COALESCE(is_retired, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Player is in an active evolution track';
    END IF;

    SELECT overall, level, date_of_birth
    INTO v_ovr, v_card_level, v_dob
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    v_age := public.card_age_from_dob(v_dob);

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

    v_xp_gain := GREATEST(
        1,
        floor(v_xp_gain * public.card_xp_age_multiplier(v_age))::INTEGER
            + public.training_ground_xp_bonus(v_tg_level)
    );

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_cost,
        -v_drill_energy,
        'stat_drill_' || p_drill_id,
        NULL,
        jsonb_build_object(
            'card_id', p_card_id,
            'drill_id', p_drill_id,
            'cost', v_cost,
            'age', v_age,
            'training_ground_level', v_tg_level
        )
    );

    UPDATE public.players
    SET daily_drill_count = v_daily + 1,
        daily_drill_reset_at = v_reset
    WHERE discord_id = p_owner_id;

    v_xp_result := public.apply_card_xp(p_card_id, v_xp_gain, 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'xp_gain', v_xp_gain,
        'cost', v_cost,
        'daily_drill_count', v_daily + 1,
        'daily_drill_limit', v_daily_limit,
        'training_ground_bonus', public.training_ground_xp_bonus(v_tg_level),
        'economy', v_econ,
        'progression', v_xp_result
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.process_recovery_session(
    p_owner_id BIGINT,
    p_player_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_energy INTEGER;
    v_daily INTEGER;
    v_reset DATE;
    v_daily_limit INTEGER := 20;
    v_player_drill_count INTEGER;
    v_player_drill_cap CONSTANT INTEGER := 5;
    v_recovery_energy INTEGER;
    v_recovery_amount INTEGER;
    v_fatigue INTEGER;
    v_old_fatigue INTEGER;
    v_injury INTEGER;
    v_in_hospital BOOLEAN;
    v_econ JSONB;
    v_gained INTEGER;
BEGIN
    PERFORM public.sync_action_energy(p_owner_id);

    SELECT action_energy, daily_drill_count, daily_drill_reset_at
    INTO v_energy, v_daily, v_reset
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.assert_card_not_on_transfer_list(p_player_card_id);

    IF v_reset IS NULL OR v_reset < CURRENT_DATE THEN
        v_daily := 0;
        v_reset := CURRENT_DATE;
    END IF;

    IF v_daily >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily drill limit reached';
    END IF;

    SELECT fatigue, injury_tier, COALESCE(in_hospital, FALSE)
    INTO v_fatigue, v_injury, v_in_hospital
    FROM public.player_cards
    WHERE id = p_player_card_id
      AND owner_id = p_owner_id
      AND COALESCE(is_retired, FALSE) = FALSE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF v_injury IS NOT NULL OR v_in_hospital THEN
        RAISE EXCEPTION 'Player is injured — use Hospital';
    END IF;

    IF v_fatigue >= 100 THEN
        RAISE EXCEPTION 'Player is already fully rested';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_player_card_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Player is in an active evolution track';
    END IF;

    INSERT INTO public.player_drill_daily_log (card_id, drill_date, count)
    VALUES (p_player_card_id, CURRENT_DATE, 1)
    ON CONFLICT (card_id, drill_date)
    DO UPDATE SET count = player_drill_daily_log.count + 1
    RETURNING count INTO v_player_drill_count;

    IF v_player_drill_count > v_player_drill_cap THEN
        RAISE EXCEPTION 'Daily drill limit reached for this player (max % per day)', v_player_drill_cap;
    END IF;

    v_recovery_energy := public.get_game_config_int('fatigue_recovery_energy', 5)::INTEGER;
    v_recovery_amount := public.get_game_config_int('fatigue_recovery_session', 40)::INTEGER;

    IF v_energy < v_recovery_energy THEN
        RAISE EXCEPTION 'Insufficient action energy';
    END IF;

    v_econ := public.apply_club_economy(
        p_owner_id,
        0,
        -v_recovery_energy,
        'recovery_session',
        NULL,
        jsonb_build_object(
            'card_id', p_player_card_id,
            'fatigue_before', v_fatigue,
            'recovery_amount', v_recovery_amount
        )
    );

    UPDATE public.players
    SET daily_drill_count = v_daily + 1,
        daily_drill_reset_at = v_reset
    WHERE discord_id = p_owner_id;

    v_old_fatigue := v_fatigue;
    v_fatigue := LEAST(100, v_fatigue + v_recovery_amount);
    v_gained := v_fatigue - v_old_fatigue;

    UPDATE public.player_cards
    SET fatigue = v_fatigue
    WHERE id = p_player_card_id;

    RETURN jsonb_build_object(
        'fatigue_gained', v_gained,
        'new_fatigue', v_fatigue,
        'energy_spent', v_recovery_energy,
        'coins_spent', 0,
        'xp_gained', 0,
        'economy', v_econ
    );
END;
$$;

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
    PERFORM public.assert_card_not_on_transfer_list(p_target_id);
    PERFORM public.assert_card_not_on_transfer_list(p_fodder_id);
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

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_target_id) THEN
        RAISE EXCEPTION 'Cannot upgrade a player card that is currently in your starting 11';
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

CREATE OR REPLACE FUNCTION public.start_player_evolution(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_track_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_active INTEGER;
    v_cooldown_hours INTEGER;
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
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.sync_action_energy(p_owner_id);

    v_max_active := public.get_game_config_int('evolution_max_active', 3)::INTEGER;
    v_cooldown_hours := public.get_game_config_int('evolution_cooldown_hours', 10)::INTEGER;

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
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);

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

CREATE OR REPLACE FUNCTION public.transfer_mentor_xp(
    p_owner_id BIGINT,
    p_source_card_id UUID,
    p_target_card_id UUID,
    p_mentor_units INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_sp_per_unit CONSTANT INTEGER := 5;
    v_xp_per_unit CONSTANT INTEGER := 500;
    v_daily_limit CONSTANT INTEGER := 3;
    v_l_max CONSTANT INTEGER := 100;
    v_units INTEGER;
    v_sp_spent INTEGER;
    v_xp_granted INTEGER;
    v_src public.player_cards%ROWTYPE;
    v_tgt public.player_cards%ROWTYPE;
    v_first UUID;
    v_second UUID;
    v_today DATE;
    v_used INTEGER;
    v_headroom INTEGER;
    v_cap_xp INTEGER;
    v_xp_result JSONB;
    v_wasted INTEGER;
BEGIN
    v_units := COALESCE(p_mentor_units, 0);
    IF v_units < 1 THEN
        RAISE EXCEPTION 'Invalid mentor unit amount';
    END IF;

    IF p_source_card_id IS NULL OR p_target_card_id IS NULL THEN
        RAISE EXCEPTION 'Source and target cards are required';
    END IF;

    IF p_source_card_id = p_target_card_id THEN
        RAISE EXCEPTION 'Source and target must differ';
    END IF;

    PERFORM public.assert_card_not_on_transfer_list(p_source_card_id);
    PERFORM public.assert_card_not_on_transfer_list(p_target_card_id);

    v_sp_spent := v_units * v_sp_per_unit;
    v_xp_granted := v_units * v_xp_per_unit;
    v_today := (timezone('utc', now()))::date;

    -- Deterministic lock order by id
    IF p_source_card_id::text < p_target_card_id::text THEN
        v_first := p_source_card_id;
        v_second := p_target_card_id;
    ELSE
        v_first := p_target_card_id;
        v_second := p_source_card_id;
    END IF;

    PERFORM 1 FROM public.player_cards WHERE id = v_first FOR UPDATE;
    PERFORM 1 FROM public.player_cards WHERE id = v_second FOR UPDATE;

    SELECT * INTO v_src FROM public.player_cards WHERE id = p_source_card_id;
    IF NOT FOUND OR v_src.owner_id IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Source card not found or not owned';
    END IF;

    SELECT * INTO v_tgt FROM public.player_cards WHERE id = p_target_card_id;
    IF NOT FOUND OR v_tgt.owner_id IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Target card not found or not owned';
    END IF;

    IF COALESCE(v_src.overall, 0) < COALESCE(v_src.potential, 0) THEN
        RAISE EXCEPTION 'Source card has not reached potential ceiling';
    END IF;

    IF COALESCE(v_src.skill_points, 0) < v_sp_spent THEN
        RAISE EXCEPTION 'Insufficient skill points';
    END IF;

    IF COALESCE(v_tgt.overall, 0) >= COALESCE(v_tgt.potential, 0) THEN
        RAISE EXCEPTION 'Target card is already maxed';
    END IF;

    IF COALESCE(v_tgt.level, 1) >= v_l_max THEN
        RAISE EXCEPTION 'Target cannot receive more XP';
    END IF;

    v_cap_xp := public.cumulative_xp_for_level(v_l_max);
    v_headroom := GREATEST(0, v_cap_xp - COALESCE(v_tgt.xp, 0));
    IF v_headroom < v_xp_granted THEN
        RAISE EXCEPTION 'Target cannot absorb mentor XP';
    END IF;

    -- Does not touch daily_alloc_count / alloc_reset_date (mentor ≠ allocate)
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.mentor_transfer_log
    WHERE club_id = p_owner_id
      AND transfer_date = v_today;

    IF v_used >= v_daily_limit THEN
        RAISE EXCEPTION 'Daily mentor transfer limit (3) reached';
    END IF;

    UPDATE public.player_cards
    SET
        skill_points = skill_points - v_sp_spent,
        skill_points_spent = skill_points_spent + v_sp_spent
    WHERE id = p_source_card_id
      AND skill_points >= v_sp_spent;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Insufficient skill points';
    END IF;

    v_xp_result := public.apply_card_xp(p_target_card_id, v_xp_granted, 'mentor_transfer');
    v_wasted := COALESCE((v_xp_result->>'xp_wasted')::INTEGER, 0);
    IF v_wasted > 0 THEN
        RAISE EXCEPTION 'Target cannot absorb mentor XP';
    END IF;

    INSERT INTO public.mentor_transfer_log (
        club_id, source_card_id, target_card_id, mentor_units, sp_spent, xp_granted, transfer_date
    ) VALUES (
        p_owner_id, p_source_card_id, p_target_card_id, v_units, v_sp_spent, v_xp_granted, v_today
    );

    v_used := v_used + 1;

    SELECT skill_points INTO v_src.skill_points
    FROM public.player_cards WHERE id = p_source_card_id;

    RETURN jsonb_build_object(
        'source_card_id', p_source_card_id,
        'target_card_id', p_target_card_id,
        'mentor_units', v_units,
        'sp_spent', v_sp_spent,
        'xp_granted', v_xp_granted,
        'source_skill_points', COALESCE(v_src.skill_points, 0),
        'xp_result', v_xp_result,
        'transfers_used_today', v_used,
        'transfers_remaining_today', GREATEST(0, v_daily_limit - v_used)
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- RLS, grants, and migration-local schema guard
-- ---------------------------------------------------------------------------

ALTER TABLE public.transfer_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transfer_sales_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS transfer_listings_select ON public.transfer_listings;
DROP POLICY IF EXISTS transfer_listings_insert ON public.transfer_listings;
DROP POLICY IF EXISTS transfer_listings_update ON public.transfer_listings;
DROP POLICY IF EXISTS transfer_sales_log_select ON public.transfer_sales_log;
DROP POLICY IF EXISTS transfer_sales_log_insert ON public.transfer_sales_log;
DROP POLICY IF EXISTS transfer_sales_log_update ON public.transfer_sales_log;

CREATE POLICY transfer_listings_select ON public.transfer_listings
    FOR SELECT TO anon, authenticated, service_role USING (true);
CREATE POLICY transfer_listings_insert ON public.transfer_listings
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);
CREATE POLICY transfer_listings_update ON public.transfer_listings
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

CREATE POLICY transfer_sales_log_select ON public.transfer_sales_log
    FOR SELECT TO anon, authenticated, service_role USING (true);
CREATE POLICY transfer_sales_log_insert ON public.transfer_sales_log
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);
CREATE POLICY transfer_sales_log_update ON public.transfer_sales_log
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE public.transfer_listings TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.transfer_sales_log TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE public.transfer_sales_log_id_seq
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.p2p_transfer_market_enabled()
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.card_is_on_transfer_list(UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.assert_card_not_on_transfer_list(UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.create_transfer_listing(BIGINT, UUID, BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.cancel_transfer_listing(BIGINT, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.purchase_transfer_listing(BIGINT, UUID, BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.expire_stale_transfer_listings()
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale(BIGINT, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.set_formation_and_assignments(BIGINT, TEXT, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.swap_squad_players(BIGINT, INTEGER, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_recovery_session(BIGINT, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.train_with_fodder(BIGINT, UUID, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.start_player_evolution(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.allocate_skill_point(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.transfer_mentor_xp(BIGINT, UUID, UUID, INTEGER)
    TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('table:public.transfer_listings'),
            ('table:public.transfer_sales_log'),
            ('function:p2p_transfer_market_enabled'),
            ('function:card_is_on_transfer_list'),
            ('function:assert_card_not_on_transfer_list'),
            ('function:create_transfer_listing'),
            ('function:cancel_transfer_listing'),
            ('function:purchase_transfer_listing'),
            ('function:expire_stale_transfer_listings'),
            ('policy:public.transfer_listings.transfer_listings_select'),
            ('policy:public.transfer_listings.transfer_listings_insert'),
            ('policy:public.transfer_listings.transfer_listings_update'),
            ('policy:public.transfer_sales_log.transfer_sales_log_select'),
            ('policy:public.transfer_sales_log.transfer_sales_log_insert'),
            ('policy:public.transfer_sales_log.transfer_sales_log_update')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'p2p_transfer_market_enabled'
                    THEN to_regprocedure('public.p2p_transfer_market_enabled()')
                WHEN 'card_is_on_transfer_list'
                    THEN to_regprocedure('public.card_is_on_transfer_list(uuid)')
                WHEN 'assert_card_not_on_transfer_list'
                    THEN to_regprocedure('public.assert_card_not_on_transfer_list(uuid)')
                WHEN 'create_transfer_listing'
                    THEN to_regprocedure('public.create_transfer_listing(bigint,uuid,bigint)')
                WHEN 'cancel_transfer_listing'
                    THEN to_regprocedure('public.cancel_transfer_listing(bigint,uuid)')
                WHEN 'purchase_transfer_listing'
                    THEN to_regprocedure('public.purchase_transfer_listing(bigint,uuid,bigint)')
                WHEN 'expire_stale_transfer_listings'
                    THEN to_regprocedure('public.expire_stale_transfer_listings()')
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
        RAISE EXCEPTION '062 schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

-- 041: Player age lifecycle — DOB, retirement, season aging batch

ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS date_of_birth DATE,
    ADD COLUMN IF NOT EXISTS is_retired BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS retirement_notified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS retired_at TIMESTAMPTZ;

-- Backfill DOB from cached age with jitter (±120 days)
UPDATE public.player_cards
SET date_of_birth = (
    CURRENT_DATE
    - (COALESCE(age, 25) || ' years')::INTERVAL
    + ((floor(random() * 241) - 120)::INT || ' days')::INTERVAL
)::DATE
WHERE date_of_birth IS NULL AND COALESCE(is_retired, FALSE) = FALSE;

UPDATE public.player_cards
SET date_of_birth = CURRENT_DATE - INTERVAL '25 years'
WHERE date_of_birth IS NULL;

ALTER TABLE public.player_cards
    ALTER COLUMN date_of_birth SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_player_cards_active_owner
    ON public.player_cards (owner_id)
    WHERE is_retired = FALSE;

INSERT INTO public.game_config (key, value_json) VALUES
    ('retirement_age', '36'),
    ('retirement_warning_age', '35'),
    ('age_xp_mult_youth', '1.5'),
    ('age_xp_mult_early_prime', '1.2'),
    ('age_xp_mult_late_prime', '1.0'),
    ('age_xp_mult_veteran', '0.7'),
    ('age_xp_mult_retiring', '0.4')
ON CONFLICT (key) DO NOTHING;

-- Whole-year age from DOB (365.25-day year), clamped 15–45
CREATE OR REPLACE FUNCTION public.card_age_from_dob(p_dob DATE, p_ref DATE DEFAULT CURRENT_DATE)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT GREATEST(15, LEAST(45, FLOOR((p_ref - p_dob) / 365.25)::INTEGER));
$$;

CREATE OR REPLACE FUNCTION public.retire_player_card(p_card_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
BEGIN
    SELECT owner_id INTO v_owner
    FROM public.player_cards
    WHERE id = p_card_id AND COALESCE(is_retired, FALSE) = FALSE
    FOR UPDATE;

    IF v_owner IS NULL THEN
        RAISE EXCEPTION 'Card not found or already retired';
    END IF;

    DELETE FROM public.squad_assignments
    WHERE player_card_id = p_card_id;

    UPDATE public.player_cards
    SET is_retired = TRUE,
        retired_at = NOW()
    WHERE id = p_card_id;

    RETURN jsonb_build_object('card_id', p_card_id, 'owner_id', v_owner, 'retired_at', NOW());
END;
$$;

CREATE OR REPLACE FUNCTION public.process_season_aging()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_new_age INTEGER;
    v_old_age INTEGER;
    v_years INTEGER;
    v_i INTEGER;
    v_retire_age INTEGER;
    v_warn_age INTEGER;
    v_retired INTEGER := 0;
    v_declined INTEGER := 0;
    v_warned INTEGER := 0;
    v_pac INTEGER;
    v_phy INTEGER;
    v_pas INTEGER;
    v_def INTEGER;
BEGIN
    v_retire_age := public.get_game_config_int('retirement_age', 36)::INTEGER;
    v_warn_age := public.get_game_config_int('retirement_warning_age', 35)::INTEGER;

    FOR v_card IN
        SELECT id, owner_id, age, date_of_birth, pac, phy, pas, def,
               retirement_notified_at, is_retired
        FROM public.player_cards
        WHERE COALESCE(is_retired, FALSE) = FALSE
        FOR UPDATE
    LOOP
        v_new_age := public.card_age_from_dob(v_card.date_of_birth);
        v_old_age := COALESCE(v_card.age, v_new_age);

        UPDATE public.player_cards SET age = v_new_age WHERE id = v_card.id;

        IF v_new_age >= v_warn_age AND v_card.retirement_notified_at IS NULL THEN
            UPDATE public.player_cards
            SET retirement_notified_at = NOW()
            WHERE id = v_card.id;
            v_warned := v_warned + 1;
        END IF;

        IF v_new_age > v_old_age THEN
            v_years := v_new_age - v_old_age;
            FOR v_i IN 1..v_years LOOP
                IF (v_old_age + v_i) >= 31 THEN
                    v_pac := GREATEST(1, v_card.pac - CASE WHEN (v_old_age + v_i) >= 35 THEN 2 ELSE 1 END);
                    v_phy := GREATEST(1, v_card.phy - CASE WHEN (v_old_age + v_i) >= 35 THEN 2 ELSE 1 END);
                    v_pas := v_card.pas;
                    v_def := v_card.def;
                    IF (v_old_age + v_i) >= 33 THEN
                        v_pas := GREATEST(1, v_card.pas - 1);
                        v_def := GREATEST(1, v_card.def - 1);
                    END IF;
                    UPDATE public.player_cards
                    SET pac = v_pac, phy = v_phy, pas = v_pas, def = v_def
                    WHERE id = v_card.id;
                    PERFORM public.recalculate_card_ovr(v_card.id);
                    v_declined := v_declined + 1;
                    SELECT pac, phy, pas, def INTO v_card.pac, v_card.phy, v_card.pas, v_card.def
                    FROM public.player_cards WHERE id = v_card.id;
                END IF;
            END LOOP;
        END IF;

        IF v_new_age >= v_retire_age THEN
            PERFORM public.retire_player_card(v_card.id);
            v_retired := v_retired + 1;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'declined_cards', v_declined,
        'retired_cards', v_retired,
        'warned_cards', v_warned
    );
END;
$$;

-- register_new_player: persist date_of_birth
CREATE OR REPLACE FUNCTION register_new_player(
    p_discord_id BIGINT,
    p_username TEXT,
    p_club_name TEXT,
    p_manager_name TEXT,
    p_cards JSONB
) RETURNS VOID AS $$
DECLARE
    v_card_record RECORD;
    v_card_id UUID;
    v_slot INT := 1;
    v_pot INT;
    v_dob DATE;
BEGIN
    IF length(trim(p_club_name)) < 1 THEN
        RAISE EXCEPTION 'Club name cannot be empty';
    END IF;
    IF length(trim(p_manager_name)) < 1 THEN
        RAISE EXCEPTION 'Manager name cannot be empty';
    END IF;

    IF EXISTS (SELECT 1 FROM public.players WHERE discord_id = p_discord_id) THEN
        RAISE EXCEPTION 'ALREADY_REGISTERED';
    END IF;

    INSERT INTO players (
        discord_id, username, club_name, manager_name,
        coins, energy, max_energy, division
    ) VALUES (
        p_discord_id, p_username, trim(p_club_name), trim(p_manager_name),
        500, 100, 100, 'Grassroots'
    );

    INSERT INTO squads (discord_id, formation) VALUES (p_discord_id, '4-4-2');

    FOR v_card_record IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE
    ) LOOP
        v_pot := COALESCE(v_card_record.potential, v_card_record.base_potential);
        IF v_pot IS NULL THEN
            RAISE EXCEPTION 'Card % missing potential', v_card_record.name;
        END IF;
        IF v_pot < v_card_record.overall THEN
            v_pot := v_card_record.overall;
        END IF;

        v_dob := COALESCE(
            v_card_record.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card_record.age, 25) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth
        ) VALUES (
            p_discord_id, v_card_record.name, v_card_record.position, v_card_record.rarity,
            v_card_record.base_rating, 1, v_card_record.overall,
            COALESCE(v_card_record.pac, 50), COALESCE(v_card_record.sho, 50),
            COALESCE(v_card_record.pas, 50), COALESCE(v_card_record.dri, 50),
            COALESCE(v_card_record.def, 50), COALESCE(v_card_record.phy, 50),
            v_pot,
            COALESCE(v_card_record.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob
        ) RETURNING id INTO v_card_id;

        INSERT INTO squad_assignments (discord_id, player_card_id, position_slot)
        VALUES (p_discord_id, v_card_id, v_slot);

        v_slot := v_slot + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- claim_daily_pack: persist date_of_birth
CREATE OR REPLACE FUNCTION public.claim_daily_pack(p_club_id BIGINT, p_cards JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_last TIMESTAMPTZ;
    v_now TIMESTAMPTZ := NOW();
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_remaining INTEGER;
    v_dob DATE;
BEGIN
    IF p_cards IS NULL OR jsonb_array_length(p_cards) < 1 THEN
        RAISE EXCEPTION 'Pack must contain at least one card';
    END IF;

    SELECT last_claim_at INTO v_last
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account not found';
    END IF;

    IF v_last IS NOT NULL AND v_now < v_last + INTERVAL '22 hours' THEN
        v_remaining := EXTRACT(EPOCH FROM (v_last + INTERVAL '22 hours' - v_now))::INTEGER;
        RAISE EXCEPTION 'COOLDOWN:%', v_remaining;
    END IF;

    UPDATE public.players SET last_claim_at = v_now WHERE discord_id = p_club_id;

    FOR v_card IN
        SELECT * FROM jsonb_to_recordset(p_cards) AS x(
            name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
            pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
            potential INT, base_potential INT, age INT, date_of_birth DATE
        )
    LOOP
        v_dob := COALESCE(
            v_card.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card.age, 25) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth
        ) VALUES (
            p_club_id,
            v_card.name,
            v_card.position,
            v_card.rarity,
            v_card.base_rating,
            1,
            v_card.overall,
            COALESCE(v_card.pac, 50),
            COALESCE(v_card.sho, 50),
            COALESCE(v_card.pas, 50),
            COALESCE(v_card.dri, 50),
            COALESCE(v_card."def", 50),
            COALESCE(v_card.phy, 50),
            COALESCE(v_card.potential, v_card.base_potential, v_card.overall),
            COALESCE(v_card.base_potential, v_card.potential, v_card.overall),
            public.card_age_from_dob(v_dob),
            v_dob
        )
        RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
    END LOOP;

    RETURN jsonb_build_object(
        'card_ids', to_jsonb(v_ids),
        'claimed_at', to_jsonb(v_now)
    );
END;
$$;

-- renew_contract: block veterans 35+
CREATE OR REPLACE FUNCTION public.renew_contract(
    p_club_id BIGINT,
    p_card_id UUID,
    p_cost BIGINT,
    p_extension_days INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    v_coins BIGINT;
    v_expiry TIMESTAMPTZ;
    v_age INTEGER;
    v_warn INTEGER;
    v_dob DATE;
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

    SELECT coins INTO v_coins FROM public.players WHERE discord_id = p_club_id;
    IF v_coins < p_cost THEN
        RAISE EXCEPTION 'Insufficient coins';
    END IF;

    UPDATE public.players SET coins = coins - p_cost WHERE discord_id = p_club_id;

    INSERT INTO public.economy_ledger (club_id, amount, currency, source)
    VALUES (p_club_id, -p_cost, 'coins', 'contract_renewal');

    SELECT contract_expires_at INTO v_expiry FROM public.player_cards WHERE id = p_card_id;
    IF v_expiry IS NULL OR v_expiry < NOW() THEN
        v_expiry := NOW();
    END IF;

    UPDATE public.player_cards
    SET contract_expires_at = v_expiry + (p_extension_days * INTERVAL '1 day')
    WHERE id = p_card_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- process_match_result: use DOB-derived age for youth POT
DROP FUNCTION IF EXISTS public.process_match_result(text, uuid[], integer, numeric[]);
DROP FUNCTION IF EXISTS public.process_match_result(text, uuid[], integer, numeric[], integer[]);

CREATE OR REPLACE FUNCTION public.process_match_result(
    p_result TEXT,
    p_card_ids UUID[],
    p_xp_amount INTEGER,
    p_card_ratings NUMERIC[] DEFAULT NULL,
    p_xp_amounts INTEGER[] DEFAULT NULL
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
    RETURN TRUE;
END;
$$;

-- Lifecycle XP multiplier (mirrors packages/player_engine/age_manager.py)
CREATE OR REPLACE FUNCTION public.card_xp_age_multiplier(p_age INTEGER)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_youth NUMERIC := public.get_game_config_numeric('age_xp_mult_youth', 1.5);
    v_early NUMERIC := public.get_game_config_numeric('age_xp_mult_early_prime', 1.2);
    v_late NUMERIC := public.get_game_config_numeric('age_xp_mult_late_prime', 1.0);
    v_vet NUMERIC := public.get_game_config_numeric('age_xp_mult_veteran', 0.7);
    v_ret NUMERIC := public.get_game_config_numeric('age_xp_mult_retiring', 0.4);
BEGIN
    IF p_age <= 21 THEN
        RETURN v_youth;
    ELSIF p_age <= 26 THEN
        RETURN v_early;
    ELSIF p_age <= 30 THEN
        RETURN v_late;
    ELSIF p_age <= 34 THEN
        RETURN v_vet;
    ELSE
        RETURN v_ret;
    END IF;
END;
$$;

DROP FUNCTION IF EXISTS public.compute_agent_offer(INTEGER, TEXT);

CREATE OR REPLACE FUNCTION public.compute_agent_offer(
    p_ovr INTEGER,
    p_rarity TEXT,
    p_age INTEGER DEFAULT NULL,
    p_potential INTEGER DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_calc_ovr INTEGER := GREATEST(45, p_ovr);
    v_base NUMERIC;
    v_mult NUMERIC := 1.0;
    v_age_factor NUMERIC := 1.0;
    v_pot_bonus NUMERIC := 1.0;
BEGIN
    v_base := power(v_calc_ovr - 45, 2.5) * 1.5 + 50;
    v_mult := CASE p_rarity
        WHEN 'Rare' THEN 1.5
        WHEN 'Epic' THEN 2.2
        WHEN 'Legendary' THEN 3.5
        ELSE 1.0
    END;

    IF p_age IS NOT NULL THEN
        IF p_age < 23 THEN
            v_age_factor := 1.2;
        ELSIF p_age <= 28 THEN
            v_age_factor := 1.0;
        ELSIF p_age <= 32 THEN
            v_age_factor := 0.8;
        ELSE
            v_age_factor := 0.5;
        END IF;
    END IF;

    IF p_potential IS NOT NULL AND p_potential > p_ovr THEN
        v_pot_bonus := 1.0 + LEAST(0.15, (p_potential - p_ovr) * 0.02);
    END IF;

    RETURN GREATEST(50, floor(v_base * v_mult * v_age_factor * v_pot_bonus))::BIGINT;
END;
$$;

CREATE OR REPLACE FUNCTION public.process_agent_sale(
    p_club_id BIGINT,
    p_card_id UUID
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ovr INTEGER;
    v_rarity TEXT;
    v_potential INTEGER;
    v_dob DATE;
    v_age INTEGER;
    v_retired BOOLEAN;
    v_sale_value BIGINT;
    v_sale_count INTEGER;
    v_cap INTEGER;
BEGIN
    PERFORM public.assert_not_in_match(p_club_id);

    v_cap := public.get_game_config_int('agent_sale_daily_cap', 10)::INTEGER;

    INSERT INTO public.agent_sale_daily_log (club_id, sale_date, count)
    VALUES (p_club_id, CURRENT_DATE, 1)
    ON CONFLICT (club_id, sale_date)
    DO UPDATE SET count = agent_sale_daily_log.count + 1
    RETURNING count INTO v_sale_count;

    IF v_sale_count > v_cap THEN
        RAISE EXCEPTION 'Daily agent sale limit reached (max % per day)', v_cap;
    END IF;

    SELECT overall, rarity, potential, date_of_birth, COALESCE(is_retired, FALSE)
    INTO v_ovr, v_rarity, v_potential, v_dob, v_retired
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_club_id
    FOR UPDATE;

    IF v_ovr IS NULL THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF v_retired THEN
        RAISE EXCEPTION 'Cannot sell a retired player';
    END IF;

    IF EXISTS (SELECT 1 FROM public.squad_assignments WHERE player_card_id = p_card_id) THEN
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
        p_club_id,
        v_sale_value,
        0,
        'agent_sale',
        'agent_sale:' || p_card_id::TEXT,
        jsonb_build_object(
            'card_id', p_card_id,
            'ovr', v_ovr,
            'rarity', v_rarity,
            'age', v_age,
            'potential', v_potential
        )
    );

    RETURN v_sale_value;
END;
$$;

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

    SELECT coins, action_energy, daily_drill_count, daily_drill_reset_at
    INTO v_coins, v_energy, v_daily, v_reset
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    PERFORM public.assert_not_in_match(p_owner_id);

    IF v_reset < CURRENT_DATE THEN
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
    );

    v_econ := public.apply_club_economy(
        p_owner_id,
        -v_cost,
        -v_drill_energy,
        'stat_drill_' || p_drill_id,
        NULL,
        jsonb_build_object('card_id', p_card_id, 'drill_id', p_drill_id, 'cost', v_cost, 'age', v_age)
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
        'economy', v_econ,
        'progression', v_xp_result
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.card_xp_age_multiplier(INTEGER) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.compute_agent_offer(INTEGER, TEXT, INTEGER, INTEGER) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_agent_sale(BIGINT, UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_stat_drill(BIGINT, UUID, TEXT) TO anon, authenticated, service_role;

GRANT ALL PRIVILEGES ON FUNCTION public.card_age_from_dob(DATE, DATE) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.retire_player_card(UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_season_aging() TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_match_result(text, uuid[], integer, numeric[], integer[])
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_daily_pack(BIGINT, JSONB)
    TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.player_cards.date_of_birth'),
            ('column:public.player_cards.is_retired'),
            ('column:public.player_cards.retirement_notified_at'),
            ('column:public.player_cards.retired_at'),
            ('function:card_age_from_dob'),
            ('function:retire_player_card'),
            ('function:process_season_aging'),
            ('function:card_xp_age_multiplier'),
            ('function:compute_agent_offer'),
            ('function:process_agent_sale'),
            ('function:process_stat_drill'),
            ('function:process_match_result'),
            ('function:claim_daily_pack')
    ) AS req(obj)
    WHERE NOT (
        (
            req.obj LIKE 'column:%'
            AND EXISTS (
                SELECT 1 FROM information_schema.columns c
                WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'card_age_from_dob' THEN to_regprocedure('public.card_age_from_dob(date,date)')
                WHEN 'retire_player_card' THEN to_regprocedure('public.retire_player_card(uuid)')
                WHEN 'process_season_aging' THEN to_regprocedure('public.process_season_aging()')
                WHEN 'card_xp_age_multiplier' THEN to_regprocedure('public.card_xp_age_multiplier(integer)')
                WHEN 'compute_agent_offer' THEN
                    to_regprocedure('public.compute_agent_offer(integer,text,integer,integer)')
                WHEN 'process_agent_sale' THEN to_regprocedure('public.process_agent_sale(bigint,uuid)')
                WHEN 'process_stat_drill' THEN to_regprocedure('public.process_stat_drill(bigint,uuid,text)')
                WHEN 'process_match_result' THEN
                    to_regprocedure('public.process_match_result(text,uuid[],integer,numeric[],integer[])')
                WHEN 'claim_daily_pack' THEN to_regprocedure('public.claim_daily_pack(bigint,jsonb)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

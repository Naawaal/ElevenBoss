-- 055: Recovery energy 5, energy max 120, CHECK relax for dual-write columns.
-- Spec: specs/010-recovery-energy-cleanup/

-- ---------------------------------------------------------------------------
-- Relax legacy energy CHECKs (001 / 015) so dual-write can store >100
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND t.relname = 'players'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%energy%'
          AND pg_get_constraintdef(c.oid) ILIKE '%100%'
    LOOP
        EXECUTE format('ALTER TABLE public.players DROP CONSTRAINT IF EXISTS %I', r.conname);
    END LOOP;
END $$;

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_energy_check;
ALTER TABLE public.players
    ADD CONSTRAINT players_energy_check CHECK (energy >= 0 AND energy <= 120);

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_training_energy_check;
ALTER TABLE public.players
    ADD CONSTRAINT players_training_energy_check CHECK (training_energy >= 0 AND training_energy <= 120);

ALTER TABLE public.players
    ALTER COLUMN energy SET DEFAULT 120,
    ALTER COLUMN max_energy SET DEFAULT 120,
    ALTER COLUMN action_energy SET DEFAULT 120,
    ALTER COLUMN training_energy SET DEFAULT 120;

UPDATE public.players
SET max_energy = 120
WHERE max_energy IS NULL OR max_energy < 120;

-- ---------------------------------------------------------------------------
-- game_config
-- ---------------------------------------------------------------------------
INSERT INTO public.game_config (key, value_json) VALUES
    ('energy_max', '120'),
    ('fatigue_recovery_energy', '5')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

-- ---------------------------------------------------------------------------
-- sync_action_energy — fallback energy_max 120
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sync_action_energy(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_energy INTEGER;
    v_max INTEGER;
    v_updated_at TIMESTAMPTZ;
    v_regen_per_min NUMERIC;
    v_minutes NUMERIC;
    v_regen INTEGER;
BEGIN
    v_max := public.get_game_config_int('energy_max', 120)::INTEGER;
    v_regen_per_min := public.get_game_config_numeric('energy_regen_per_min', 0.1666667);

    SELECT action_energy, action_energy_updated_at
    INTO v_energy, v_updated_at
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found';
    END IF;

    v_energy := COALESCE(v_energy, v_max);
    v_updated_at := COALESCE(v_updated_at, NOW());

    v_minutes := EXTRACT(EPOCH FROM (NOW() - v_updated_at)) / 60.0;
    IF v_minutes > 0 AND v_energy < v_max THEN
        v_regen := floor(v_minutes * v_regen_per_min)::INTEGER;
        v_energy := LEAST(v_max, v_energy + v_regen);
    END IF;

    UPDATE public.players
    SET
        action_energy = v_energy,
        action_energy_updated_at = NOW(),
        energy = v_energy,
        training_energy = v_energy
    WHERE discord_id = p_club_id;

    RETURN jsonb_build_object(
        'action_energy', v_energy,
        'max_energy', v_max,
        'regen_per_min', v_regen_per_min
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- apply_club_economy — fallback energy_max 120 (body from 047)
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

    v_max := public.get_game_config_int('energy_max', 120)::INTEGER;
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
-- process_recovery_session — fallback fatigue_recovery_energy 5
-- ---------------------------------------------------------------------------
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

GRANT ALL PRIVILEGES ON FUNCTION public.process_recovery_session(BIGINT, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.sync_action_energy(BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.apply_club_economy(BIGINT, BIGINT, INTEGER, TEXT, TEXT, JSONB)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- register_new_player — seed energy/max at 120
-- ---------------------------------------------------------------------------
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
        coins, energy, max_energy, action_energy, division
    ) VALUES (
        p_discord_id, p_username, trim(p_club_name), trim(p_manager_name),
        500, 120, 120, 120, 'Grassroots'
    );

    INSERT INTO squads (discord_id, formation) VALUES (p_discord_id, '4-4-2');

    FOR v_card_record IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
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
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
        ) VALUES (
            p_discord_id, v_card_record.name, v_card_record.position, v_card_record.rarity,
            v_card_record.base_rating, 1, v_card_record.overall,
            COALESCE(v_card_record.pac, 50), COALESCE(v_card_record.sho, 50),
            COALESCE(v_card_record.pas, 50), COALESCE(v_card_record.dri, 50),
            COALESCE(v_card_record.def, 50), COALESCE(v_card_record.phy, 50),
            v_pot,
            COALESCE(v_card_record.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob,
            COALESCE(NULLIF(trim(v_card_record.role), ''), 'Balanced')
        ) RETURNING id INTO v_card_id;

        INSERT INTO squad_assignments (discord_id, player_card_id, position_slot)
        VALUES (p_discord_id, v_card_id, v_slot);

        v_slot := v_slot + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF public.get_game_config_int('energy_max', 0) <> 120 THEN
        RAISE EXCEPTION 'Migration 055 guard failed — energy_max != 120';
    END IF;
    IF public.get_game_config_int('fatigue_recovery_energy', 0) <> 5 THEN
        RAISE EXCEPTION 'Migration 055 guard failed — fatigue_recovery_energy != 5';
    END IF;
END $$;

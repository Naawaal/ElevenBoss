-- 074: US-42.1 Identity & Ownership
-- Soft lifecycle columns, concurrent-safe register_new_player, touch/classify/recover RPCs.

-- ---------------------------------------------------------------------------
-- Soft lifecycle columns on players
-- ---------------------------------------------------------------------------
ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS identity_status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE public.players
    DROP CONSTRAINT IF EXISTS players_identity_status_check;

ALTER TABLE public.players
    ADD CONSTRAINT players_identity_status_check
    CHECK (identity_status IN ('active', 'inactive', 'abandoned'));

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS last_qualifying_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS identity_status_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE public.players
SET
    last_qualifying_activity_at = COALESCE(last_qualifying_activity_at, created_at, NOW()),
    identity_status_changed_at = COALESCE(identity_status_changed_at, created_at, NOW()),
    identity_status = COALESCE(identity_status, 'active')
WHERE TRUE;

-- ---------------------------------------------------------------------------
-- register_new_player — race-safe ALREADY_REGISTERED + identity columns
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

    BEGIN
        INSERT INTO players (
            discord_id, username, club_name, manager_name,
            coins, energy, max_energy, action_energy, division,
            is_ai, identity_status, last_qualifying_activity_at, identity_status_changed_at
        ) VALUES (
            p_discord_id, p_username, trim(p_club_name), trim(p_manager_name),
            500, 120, 120, 120, 'Grassroots',
            FALSE, 'active', NOW(), NOW()
        );
    EXCEPTION
        WHEN unique_violation THEN
            RAISE EXCEPTION 'ALREADY_REGISTERED';
    END;

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

-- ---------------------------------------------------------------------------
-- Soft lifecycle RPCs
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.touch_club_activity(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_old TEXT;
    v_new TEXT;
BEGIN
    SELECT identity_status INTO v_old
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    v_new := v_old;
    IF v_old IN ('inactive', 'abandoned') THEN
        v_new := 'active';
    END IF;

    UPDATE public.players
    SET
        last_qualifying_activity_at = NOW(),
        identity_status = v_new,
        identity_status_changed_at = CASE
            WHEN v_new IS DISTINCT FROM v_old THEN NOW()
            ELSE identity_status_changed_at
        END
    WHERE discord_id = p_club_id;

    RETURN jsonb_build_object(
        'discord_id', p_club_id,
        'old_status', v_old,
        'new_status', v_new,
        'last_qualifying_activity_at', NOW()
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.classify_club_identity_status(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_is_ai BOOLEAN;
    v_old TEXT;
    v_new TEXT;
    v_last TIMESTAMPTZ;
    v_days NUMERIC;
    v_inactive_days CONSTANT INTEGER := 30;
    v_abandoned_days CONSTANT INTEGER := 90;
BEGIN
    SELECT is_ai, identity_status, last_qualifying_activity_at
    INTO v_is_ai, v_old, v_last
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    IF COALESCE(v_is_ai, FALSE) THEN
        RETURN jsonb_build_object(
            'discord_id', p_club_id,
            'old_status', v_old,
            'new_status', v_old,
            'skipped', TRUE,
            'reason', 'ai_club'
        );
    END IF;

    v_days := EXTRACT(EPOCH FROM (NOW() - v_last)) / 86400.0;
    IF v_days >= v_abandoned_days THEN
        v_new := 'abandoned';
    ELSIF v_days >= v_inactive_days THEN
        v_new := 'inactive';
    ELSE
        v_new := 'active';
    END IF;

    IF v_new IS DISTINCT FROM v_old THEN
        UPDATE public.players
        SET
            identity_status = v_new,
            identity_status_changed_at = NOW()
        WHERE discord_id = p_club_id;
    END IF;

    RETURN jsonb_build_object(
        'discord_id', p_club_id,
        'old_status', v_old,
        'new_status', v_new,
        'days_since_activity', round(v_days::numeric, 2),
        'skipped', FALSE
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.recover_club_identity(p_club_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_old TEXT;
BEGIN
    SELECT identity_status INTO v_old
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    UPDATE public.players
    SET
        identity_status = 'active',
        last_qualifying_activity_at = NOW(),
        identity_status_changed_at = CASE
            WHEN v_old IS DISTINCT FROM 'active' THEN NOW()
            ELSE identity_status_changed_at
        END
    WHERE discord_id = p_club_id;

    RETURN jsonb_build_object(
        'discord_id', p_club_id,
        'old_status', v_old,
        'new_status', 'active'
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.touch_club_activity(BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.classify_club_identity_status(BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.recover_club_identity(BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.register_new_player(BIGINT, TEXT, TEXT, TEXT, JSONB)
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
            ('column:public.players.identity_status'),
            ('column:public.players.last_qualifying_activity_at'),
            ('column:public.players.identity_status_changed_at'),
            ('function:touch_club_activity'),
            ('function:classify_club_identity_status'),
            ('function:recover_club_identity'),
            ('function:register_new_player')
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
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'touch_club_activity'
                    THEN to_regprocedure('public.touch_club_activity(bigint)')
                WHEN 'classify_club_identity_status'
                    THEN to_regprocedure('public.classify_club_identity_status(bigint)')
                WHEN 'recover_club_identity'
                    THEN to_regprocedure('public.recover_club_identity(bigint)')
                WHEN 'register_new_player'
                    THEN to_regprocedure('public.register_new_player(bigint,text,text,text,jsonb)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 074 guard failed — missing: %', v_missing;
    END IF;
END $$;

-- 042: Seasonal youth academy intake (Phase B — flat L1 quality for all clubs)

CREATE TABLE IF NOT EXISTS public.youth_intake_log (
    owner_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    intake_week  DATE NOT NULL,
    card_ids     UUID[] NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notified_at  TIMESTAMPTZ,
    PRIMARY KEY (owner_id, intake_week)
);

INSERT INTO public.game_config (key, value_json) VALUES
    ('youth_intake_count', '3'),
    ('youth_intake_academy_level', '1')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.current_intake_week(p_ref TIMESTAMPTZ DEFAULT NOW())
RETURNS DATE
LANGUAGE sql
STABLE
AS $$
    SELECT (date_trunc('week', (p_ref AT TIME ZONE 'UTC')::timestamp))::DATE;
$$;

CREATE OR REPLACE FUNCTION public.process_youth_intake(
    p_owner_id BIGINT,
    p_cards JSONB
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_week DATE;
    v_existing UUID[];
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_count INTEGER;
    v_dob DATE;
    v_pot INT;
BEGIN
    IF p_cards IS NULL OR jsonb_array_length(p_cards) < 1 THEN
        RAISE EXCEPTION 'Intake must contain at least one card';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.players
        WHERE discord_id = p_owner_id AND COALESCE(is_ai, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Manager not found';
    END IF;

    v_week := public.current_intake_week();

    SELECT card_ids INTO v_existing
    FROM public.youth_intake_log
    WHERE owner_id = p_owner_id AND intake_week = v_week;

    IF v_existing IS NOT NULL THEN
        RETURN jsonb_build_object(
            'owner_id', p_owner_id,
            'intake_week', v_week,
            'card_ids', to_jsonb(v_existing),
            'already_processed', TRUE
        );
    END IF;

    v_count := public.get_game_config_int('youth_intake_count', 3)::INTEGER;
    IF jsonb_array_length(p_cards) > v_count THEN
        RAISE EXCEPTION 'Intake exceeds max cards (%)', v_count;
    END IF;

    FOR v_card IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE
    ) LOOP
        v_pot := COALESCE(v_card.potential, v_card.base_potential);
        IF v_pot IS NULL THEN
            RAISE EXCEPTION 'Card % missing potential', v_card.name;
        END IF;
        IF v_pot < v_card.overall THEN
            v_pot := v_card.overall;
        END IF;

        v_dob := COALESCE(
            v_card.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card.age, 18) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth
        ) VALUES (
            p_owner_id, v_card.name, v_card.position, v_card.rarity,
            v_card.base_rating, 1, v_card.overall,
            COALESCE(v_card.pac, 50), COALESCE(v_card.sho, 50),
            COALESCE(v_card.pas, 50), COALESCE(v_card.dri, 50),
            COALESCE(v_card.def, 50), COALESCE(v_card.phy, 50),
            v_pot,
            COALESCE(v_card.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob
        ) RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
    END LOOP;

    INSERT INTO public.youth_intake_log (owner_id, intake_week, card_ids)
    VALUES (p_owner_id, v_week, v_ids);

    RETURN jsonb_build_object(
        'owner_id', p_owner_id,
        'intake_week', v_week,
        'card_ids', to_jsonb(v_ids),
        'already_processed', FALSE
    );
END;
$$;

GRANT ALL PRIVILEGES ON TABLE public.youth_intake_log TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.current_intake_week(TIMESTAMPTZ) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_youth_intake(BIGINT, JSONB) TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('table:public.youth_intake_log'),
            ('function:current_intake_week'),
            ('function:process_youth_intake')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'current_intake_week' THEN to_regprocedure('public.current_intake_week(timestamp with time zone)')
                WHEN 'process_youth_intake' THEN to_regprocedure('public.process_youth_intake(bigint,jsonb)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

-- 044: Scouting pool / regen market (Phase D)

CREATE TABLE IF NOT EXISTS public.scouting_pool_players (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_card_id   UUID UNIQUE,
    name             TEXT NOT NULL,
    position         TEXT NOT NULL CHECK (position IN ('GK', 'DEF', 'MID', 'FWD')),
    rarity           TEXT NOT NULL CHECK (rarity IN ('Common', 'Rare', 'Epic', 'Legendary')),
    base_rating      INTEGER NOT NULL,
    overall          INTEGER NOT NULL,
    pac              INTEGER NOT NULL DEFAULT 50,
    sho              INTEGER NOT NULL DEFAULT 50,
    pas              INTEGER NOT NULL DEFAULT 50,
    dri              INTEGER NOT NULL DEFAULT 50,
    "def"            INTEGER NOT NULL DEFAULT 50,
    phy              INTEGER NOT NULL DEFAULT 50,
    potential        INTEGER NOT NULL,
    base_potential   INTEGER NOT NULL,
    age              INTEGER NOT NULL,
    date_of_birth    DATE NOT NULL,
    list_price       BIGINT NOT NULL,
    claimed_by       BIGINT REFERENCES public.players(discord_id) ON DELETE SET NULL,
    claimed_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scouting_pool_available
    ON public.scouting_pool_players (created_at DESC)
    WHERE claimed_by IS NULL;

INSERT INTO public.game_config (key, value_json) VALUES
    ('regen_ovr_threshold', '75'),
    ('scouting_pool_max_active', '50')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.insert_scouting_pool_player(p_card JSONB)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_id UUID;
    v_source UUID;
    v_pot INT;
    v_dob DATE;
    v_max INTEGER;
BEGIN
    v_source := NULLIF(p_card->>'source_card_id', '')::UUID;
    IF v_source IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.scouting_pool_players WHERE source_card_id = v_source
    ) THEN
        SELECT id INTO v_id FROM public.scouting_pool_players WHERE source_card_id = v_source;
        RETURN v_id;
    END IF;

    v_max := public.get_game_config_int('scouting_pool_max_active', 50)::INTEGER;
    IF (SELECT COUNT(*) FROM public.scouting_pool_players WHERE claimed_by IS NULL) >= v_max THEN
        DELETE FROM public.scouting_pool_players
        WHERE id IN (
            SELECT id FROM public.scouting_pool_players
            WHERE claimed_by IS NULL
            ORDER BY created_at ASC
            LIMIT 1
        );
    END IF;

    v_pot := COALESCE((p_card->>'potential')::INT, (p_card->>'base_potential')::INT);
    v_dob := COALESCE((p_card->>'date_of_birth')::DATE, CURRENT_DATE - INTERVAL '18 years');

    INSERT INTO public.scouting_pool_players (
        source_card_id, name, position, rarity, base_rating, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, list_price
    ) VALUES (
        v_source,
        p_card->>'name',
        p_card->>'position',
        p_card->>'rarity',
        COALESCE((p_card->>'base_rating')::INT, (p_card->>'overall')::INT),
        (p_card->>'overall')::INT,
        COALESCE((p_card->>'pac')::INT, 50),
        COALESCE((p_card->>'sho')::INT, 50),
        COALESCE((p_card->>'pas')::INT, 50),
        COALESCE((p_card->>'dri')::INT, 50),
        COALESCE((p_card->>'def')::INT, 50),
        COALESCE((p_card->>'phy')::INT, 50),
        v_pot,
        COALESCE((p_card->>'base_potential')::INT, v_pot),
        COALESCE((p_card->>'age')::INT, public.card_age_from_dob(v_dob)),
        v_dob,
        COALESCE((p_card->>'list_price')::BIGINT, 500)
    ) RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

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
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth
    ) VALUES (
        p_buyer_id, v_row.name, v_row.position, v_row.rarity,
        v_row.base_rating, 1, v_row.overall,
        v_row.pac, v_row.sho, v_row.pas, v_row.dri, v_row.def, v_row.phy,
        v_row.potential, v_row.base_potential, v_row.age, v_row.date_of_birth
    ) RETURNING id INTO v_card_id;

    UPDATE public.scouting_pool_players
    SET claimed_by = p_buyer_id, claimed_at = NOW()
    WHERE id = p_pool_id;

    RETURN jsonb_build_object(
        'pool_id', p_pool_id,
        'card_id', v_card_id,
        'coins_spent', v_row.list_price,
        'player_name', v_row.name
    );
END;
$$;

ALTER TABLE public.scouting_pool_players ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scouting_pool_select ON public.scouting_pool_players;
DROP POLICY IF EXISTS scouting_pool_insert ON public.scouting_pool_players;
DROP POLICY IF EXISTS scouting_pool_update ON public.scouting_pool_players;

CREATE POLICY scouting_pool_select ON public.scouting_pool_players
    FOR SELECT TO anon, authenticated, service_role USING (true);

CREATE POLICY scouting_pool_insert ON public.scouting_pool_players
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

CREATE POLICY scouting_pool_update ON public.scouting_pool_players
    FOR UPDATE TO anon, authenticated, service_role USING (true);

GRANT ALL PRIVILEGES ON TABLE public.scouting_pool_players TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.insert_scouting_pool_player(JSONB) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.purchase_scouting_player(BIGINT, UUID, BIGINT) TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('table:public.scouting_pool_players'),
            ('function:insert_scouting_pool_player'),
            ('function:purchase_scouting_player'),
            ('policy:public.scouting_pool_players.scouting_pool_select'),
            ('policy:public.scouting_pool_players.scouting_pool_insert'),
            ('policy:public.scouting_pool_players.scouting_pool_update')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'insert_scouting_pool_player' THEN to_regprocedure('public.insert_scouting_pool_player(jsonb)')
                WHEN 'purchase_scouting_player' THEN to_regprocedure('public.purchase_scouting_player(bigint,uuid,bigint)')
                ELSE NULL
            END IS NOT NULL
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
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

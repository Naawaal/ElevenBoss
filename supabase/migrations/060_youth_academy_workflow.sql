-- 060: Youth Academy workflow — holding phase, growth, promote/release, paid scouting
-- Spec: specs/015-youth-academy/

-- ---------------------------------------------------------------------------
-- Columns
-- ---------------------------------------------------------------------------
ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS in_academy BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS academy_progress INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS academy_seated_at TIMESTAMPTZ;

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS scouting_finishes_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS scouting_active_tier TEXT;

CREATE INDEX IF NOT EXISTS idx_player_cards_academy_owner
    ON public.player_cards (owner_id)
    WHERE in_academy = TRUE;

-- ---------------------------------------------------------------------------
-- Scouting reports
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.scouting_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    tier            TEXT NOT NULL CHECK (tier IN ('quick', 'standard', 'deep')),
    prospects_json  JSONB NOT NULL,
    signed_card_id  UUID REFERENCES public.player_cards(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    notified_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scouting_reports_owner_expires
    ON public.scouting_reports (owner_id, expires_at DESC);

ALTER TABLE public.scouting_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scouting_reports_select ON public.scouting_reports;
DROP POLICY IF EXISTS scouting_reports_insert ON public.scouting_reports;
DROP POLICY IF EXISTS scouting_reports_update ON public.scouting_reports;

CREATE POLICY scouting_reports_select ON public.scouting_reports
    FOR SELECT TO anon, authenticated, service_role USING (true);

CREATE POLICY scouting_reports_insert ON public.scouting_reports
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

CREATE POLICY scouting_reports_update ON public.scouting_reports
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE public.scouting_reports TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- game_config
-- ---------------------------------------------------------------------------
INSERT INTO public.game_config (key, value_json) VALUES
    ('senior_roster_cap', '48'),
    ('scout_cost_quick', '3000'),
    ('scout_cost_standard', '10000'),
    ('scout_cost_deep', '25000'),
    ('scout_hours_quick', '2'),
    ('scout_hours_standard', '8'),
    ('scout_hours_deep', '24'),
    ('scout_report_ttl_hours', '48'),
    ('academy_ready_ovr', '65'),
    ('academy_age_out', '20')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.academy_slot_cap(p_level INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE GREATEST(1, LEAST(5, COALESCE(p_level, 1)))
        WHEN 1 THEN 4
        WHEN 2 THEN 5
        WHEN 3 THEN 6
        WHEN 4 THEN 8
        ELSE 10
    END;
$$;

CREATE OR REPLACE FUNCTION public.academy_daily_points(p_level INTEGER, p_potential INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT 10 + (5 * GREATEST(1, LEAST(5, COALESCE(p_level, 1))))
         + (GREATEST(0, COALESCE(p_potential, 0)) / 25);
$$;

CREATE OR REPLACE FUNCTION public.academy_bump_primary_stat(
    p_position TEXT,
    p_pac INT, p_sho INT, p_pas INT, p_dri INT, p_def INT, p_phy INT,
    p_potential INT
) RETURNS TABLE(pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT)
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_cap INT := GREATEST(1, LEAST(99, COALESCE(p_potential, 99)));
    v_pac INT := COALESCE(p_pac, 50);
    v_sho INT := COALESCE(p_sho, 50);
    v_pas INT := COALESCE(p_pas, 50);
    v_dri INT := COALESCE(p_dri, 50);
    v_def INT := COALESCE(p_def, 50);
    v_phy INT := COALESCE(p_phy, 50);
    v_order TEXT[];
    v_attr TEXT;
BEGIN
    v_order := CASE COALESCE(p_position, 'MID')
        WHEN 'FWD' THEN ARRAY['sho', 'pac', 'dri', 'phy', 'pas', 'def']
        WHEN 'DEF' THEN ARRAY['def', 'phy', 'pac', 'pas', 'dri', 'sho']
        WHEN 'GK'  THEN ARRAY['def', 'phy', 'pas', 'pac', 'dri', 'sho']
        ELSE ARRAY['pas', 'dri', 'pac', 'def', 'phy', 'sho']
    END;
    FOREACH v_attr IN ARRAY v_order LOOP
        IF v_attr = 'pac' AND v_pac < v_cap AND v_pac < 99 THEN
            v_pac := v_pac + 1; EXIT;
        ELSIF v_attr = 'sho' AND v_sho < v_cap AND v_sho < 99 THEN
            v_sho := v_sho + 1; EXIT;
        ELSIF v_attr = 'pas' AND v_pas < v_cap AND v_pas < 99 THEN
            v_pas := v_pas + 1; EXIT;
        ELSIF v_attr = 'dri' AND v_dri < v_cap AND v_dri < 99 THEN
            v_dri := v_dri + 1; EXIT;
        ELSIF v_attr = 'def' AND v_def < v_cap AND v_def < 99 THEN
            v_def := v_def + 1; EXIT;
        ELSIF v_attr = 'phy' AND v_phy < v_cap AND v_phy < 99 THEN
            v_phy := v_phy + 1; EXIT;
        END IF;
    END LOOP;
    RETURN QUERY SELECT v_pac, v_sho, v_pas, v_dri, v_def, v_phy;
END;
$$;

-- ---------------------------------------------------------------------------
-- process_youth_intake — academy seating (partial seat / skip remainder)
-- ---------------------------------------------------------------------------
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
    v_level INTEGER;
    v_cap INTEGER;
    v_used INTEGER;
    v_free INTEGER;
    v_seated INTEGER := 0;
    v_skipped INTEGER := 0;
    v_idx INTEGER := 0;
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
        SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
        v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
        SELECT COUNT(*)::INTEGER INTO v_used
        FROM public.player_cards
        WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
        RETURN jsonb_build_object(
            'owner_id', p_owner_id,
            'intake_week', v_week,
            'card_ids', to_jsonb(v_existing),
            'seated', COALESCE(array_length(v_existing, 1), 0),
            'skipped', 0,
            'slots_used', COALESCE(v_used, 0),
            'slots_cap', v_cap,
            'already_processed', TRUE
        );
    END IF;

    v_count := public.get_game_config_int('youth_intake_count', 3)::INTEGER;
    IF jsonb_array_length(p_cards) > v_count THEN
        RAISE EXCEPTION 'Intake exceeds max cards (%)', v_count;
    END IF;

    SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
    v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.player_cards
    WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
    v_free := GREATEST(0, v_cap - COALESCE(v_used, 0));

    FOR v_card IN SELECT * FROM jsonb_to_recordset(p_cards) AS x(
        name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
        pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
        potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
    ) LOOP
        v_idx := v_idx + 1;
        IF v_seated >= v_free THEN
            v_skipped := v_skipped + 1;
            CONTINUE;
        END IF;

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
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
            in_academy, academy_progress, academy_seated_at
        ) VALUES (
            p_owner_id, v_card.name, v_card.position, v_card.rarity,
            v_card.base_rating, 1, v_card.overall,
            COALESCE(v_card.pac, 50), COALESCE(v_card.sho, 50),
            COALESCE(v_card.pas, 50), COALESCE(v_card.dri, 50),
            COALESCE(v_card.def, 50), COALESCE(v_card.phy, 50),
            v_pot,
            COALESCE(v_card.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob,
            COALESCE(NULLIF(trim(v_card.role), ''), 'Balanced'),
            TRUE, 0, NOW()
        ) RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
        v_seated := v_seated + 1;
    END LOOP;

    INSERT INTO public.youth_intake_log (owner_id, intake_week, card_ids)
    VALUES (p_owner_id, v_week, v_ids);

    RETURN jsonb_build_object(
        'owner_id', p_owner_id,
        'intake_week', v_week,
        'card_ids', to_jsonb(v_ids),
        'seated', v_seated,
        'skipped', v_skipped,
        'slots_used', COALESCE(v_used, 0) + v_seated,
        'slots_cap', v_cap,
        'already_processed', FALSE
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- promote / release
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.promote_academy_player(
    p_owner_id BIGINT,
    p_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_senior INTEGER;
    v_cap INTEGER;
    v_ready INTEGER;
    v_ovr INTEGER;
BEGIN
    SELECT * INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Card not found';
    END IF;
    IF COALESCE(v_card.is_retired, FALSE) THEN
        RAISE EXCEPTION 'Card is retired';
    END IF;
    IF NOT COALESCE(v_card.in_academy, FALSE) THEN
        RAISE EXCEPTION 'Not an academy player';
    END IF;

    v_cap := public.get_game_config_int('senior_roster_cap', 48)::INTEGER;
    SELECT COUNT(*)::INTEGER INTO v_senior
    FROM public.player_cards
    WHERE owner_id = p_owner_id
      AND in_academy = FALSE
      AND COALESCE(is_retired, FALSE) = FALSE;

    IF v_senior >= v_cap THEN
        RAISE EXCEPTION 'Senior roster is full (%/%). Sell or release a senior player first.', v_senior, v_cap;
    END IF;

    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;

    UPDATE public.player_cards
    SET in_academy = FALSE,
        academy_progress = 0,
        academy_seated_at = NULL
    WHERE id = p_card_id;

    v_ready := public.get_game_config_int('academy_ready_ovr', 65)::INTEGER;
    v_ovr := v_card.overall;

    RETURN jsonb_build_object(
        'card_id', p_card_id,
        'overall', v_ovr,
        'potential', v_card.potential,
        'early_promote', v_ovr < v_ready
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.release_academy_player(
    p_owner_id BIGINT,
    p_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_name TEXT;
BEGIN
    SELECT name INTO v_name
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id AND in_academy = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Not an academy player';
    END IF;

    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;
    DELETE FROM public.player_cards WHERE id = p_card_id;

    RETURN jsonb_build_object(
        'released_card_id', p_card_id,
        'name', v_name
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Daily academy growth + age-out
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_daily_academy_growth()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_card RECORD;
    v_level INTEGER;
    v_points INTEGER;
    v_prog INTEGER;
    v_ovr INTEGER;
    v_pot INTEGER;
    v_gained INTEGER;
    v_bump RECORD;
    v_age INTEGER;
    v_age_out INTEGER;
    v_ready INTEGER;
    v_ticked INTEGER := 0;
    v_promoted JSONB := '[]'::JSONB;
    v_released JSONB := '[]'::JSONB;
    v_promo JSONB;
BEGIN
    v_age_out := public.get_game_config_int('academy_age_out', 20)::INTEGER;
    v_ready := public.get_game_config_int('academy_ready_ovr', 65)::INTEGER;

    FOR v_card IN
        SELECT pc.*, p.youth_academy_level
        FROM public.player_cards pc
        JOIN public.players p ON p.discord_id = pc.owner_id
        WHERE pc.in_academy = TRUE
          AND COALESCE(pc.is_retired, FALSE) = FALSE
          AND COALESCE(p.is_ai, FALSE) = FALSE
        FOR UPDATE OF pc
    LOOP
        v_level := COALESCE(v_card.youth_academy_level, 1);
        v_pot := GREATEST(v_card.overall, COALESCE(v_card.potential, v_card.overall));
        v_ovr := LEAST(v_card.overall, v_pot);
        v_prog := COALESCE(v_card.academy_progress, 0);
        v_points := public.academy_daily_points(v_level, v_pot);
        v_prog := v_prog + v_points;
        v_gained := 0;

        WHILE v_prog >= 100 AND v_ovr < v_pot LOOP
            v_ovr := v_ovr + 1;
            v_prog := v_prog - 100;
            v_gained := v_gained + 1;
            SELECT * INTO v_bump FROM public.academy_bump_primary_stat(
                v_card.position, v_card.pac, v_card.sho, v_card.pas, v_card.dri, v_card."def", v_card.phy, v_pot
            );
            v_card.pac := v_bump.pac;
            v_card.sho := v_bump.sho;
            v_card.pas := v_bump.pas;
            v_card.dri := v_bump.dri;
            v_card."def" := v_bump."def";
            v_card.phy := v_bump.phy;
        END LOOP;

        UPDATE public.player_cards
        SET overall = v_ovr,
            academy_progress = v_prog,
            pac = v_card.pac,
            sho = v_card.sho,
            pas = v_card.pas,
            dri = v_card.dri,
            "def" = v_card."def",
            phy = v_card.phy,
            age = public.card_age_from_dob(date_of_birth)
        WHERE id = v_card.id;

        v_ticked := v_ticked + 1;

        v_age := public.card_age_from_dob(v_card.date_of_birth);
        IF v_age >= v_age_out THEN
            BEGIN
                v_promo := public.promote_academy_player(v_card.owner_id, v_card.id);
                v_promoted := v_promoted || jsonb_build_array(jsonb_build_object(
                    'owner_id', v_card.owner_id,
                    'card_id', v_card.id,
                    'name', v_card.name,
                    'result', 'promoted',
                    'early_promote', v_promo->>'early_promote'
                ));
            EXCEPTION WHEN OTHERS THEN
                PERFORM public.release_academy_player(v_card.owner_id, v_card.id);
                v_released := v_released || jsonb_build_array(jsonb_build_object(
                    'owner_id', v_card.owner_id,
                    'card_id', v_card.id,
                    'name', v_card.name,
                    'result', 'released',
                    'reason', SQLERRM
                ));
            END;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'ticked', v_ticked,
        'age_out_promoted', v_promoted,
        'age_out_released', v_released,
        'ready_ovr', v_ready
    );
END;
$$;
-- ---------------------------------------------------------------------------
-- Scouting RPCs
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.dispatch_youth_scout(
    p_owner_id BIGINT,
    p_tier TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_tier TEXT := lower(trim(p_tier));
    v_cost BIGINT;
    v_hours INTEGER;
    v_finishes TIMESTAMPTZ;
    v_eco JSONB;
    v_coins BIGINT;
BEGIN
    IF v_tier NOT IN ('quick', 'standard', 'deep') THEN
        RAISE EXCEPTION 'Invalid scout tier';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.players
        WHERE discord_id = p_owner_id AND COALESCE(is_ai, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Manager not found';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.players
        WHERE discord_id = p_owner_id
          AND scouting_finishes_at IS NOT NULL
          AND scouting_finishes_at > NOW()
    ) THEN
        RAISE EXCEPTION 'Scout already in progress';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.scouting_reports
        WHERE owner_id = p_owner_id
          AND signed_card_id IS NULL
          AND expires_at > NOW()
    ) THEN
        RAISE EXCEPTION 'Claimable scout report already open';
    END IF;

    v_cost := public.get_game_config_int('scout_cost_' || v_tier, 3000);
    v_hours := public.get_game_config_int('scout_hours_' || v_tier, 2)::INTEGER;
    v_finishes := NOW() + make_interval(hours => v_hours);

    v_eco := public.apply_club_economy(
        p_owner_id,
        -v_cost,
        0,
        'youth_scout_' || v_tier,
        'scout:' || p_owner_id::TEXT || ':' || v_tier || ':' || v_finishes::TEXT,
        jsonb_build_object('tier', v_tier)
    );

    UPDATE public.players
    SET scouting_finishes_at = v_finishes,
        scouting_active_tier = v_tier
    WHERE discord_id = p_owner_id;

    SELECT coins INTO v_coins FROM public.players WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object(
        'tier', v_tier,
        'finishes_at', v_finishes,
        'cost', v_cost,
        'coins_remaining', v_coins,
        'economy', v_eco
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.finalize_youth_scout_report(
    p_owner_id BIGINT,
    p_prospects JSONB,
    p_tier TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_finishes TIMESTAMPTZ;
    v_stored_tier TEXT;
    v_tier TEXT;
    v_ttl INTEGER;
    v_id UUID;
    v_expires TIMESTAMPTZ;
BEGIN
    SELECT scouting_finishes_at, scouting_active_tier
    INTO v_finishes, v_stored_tier
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF v_finishes IS NULL THEN
        RAISE EXCEPTION 'No scout assignment to finalize';
    END IF;
    IF v_finishes > NOW() THEN
        RAISE EXCEPTION 'Scout assignment still in progress';
    END IF;

    IF p_prospects IS NULL OR jsonb_typeof(p_prospects) <> 'array'
       OR jsonb_array_length(p_prospects) <> 3 THEN
        RAISE EXCEPTION 'Scout report must contain exactly 3 prospects';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.scouting_reports
        WHERE owner_id = p_owner_id
          AND signed_card_id IS NULL
          AND expires_at > NOW()
    ) THEN
        RAISE EXCEPTION 'Claimable scout report already open';
    END IF;

    v_tier := lower(COALESCE(NULLIF(trim(p_tier), ''), NULLIF(trim(v_stored_tier), ''), 'standard'));
    IF v_tier NOT IN ('quick', 'standard', 'deep') THEN
        v_tier := 'standard';
    END IF;

    v_ttl := public.get_game_config_int('scout_report_ttl_hours', 48)::INTEGER;
    v_expires := NOW() + make_interval(hours => v_ttl);

    INSERT INTO public.scouting_reports (owner_id, tier, prospects_json, expires_at)
    VALUES (p_owner_id, v_tier, p_prospects, v_expires)
    RETURNING id INTO v_id;

    UPDATE public.players
    SET scouting_finishes_at = NULL,
        scouting_active_tier = NULL
    WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object(
        'report_id', v_id,
        'expires_at', v_expires,
        'tier', v_tier
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

    RETURN jsonb_build_object(
        'card_id', v_card_id,
        'report_id', p_report_id,
        'index', p_index
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.academy_slot_cap(INTEGER) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.academy_daily_points(INTEGER, INTEGER) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.academy_bump_primary_stat(TEXT, INT, INT, INT, INT, INT, INT, INT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_youth_intake(BIGINT, JSONB) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.promote_academy_player(BIGINT, UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.release_academy_player(BIGINT, UUID) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.process_daily_academy_growth() TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.dispatch_youth_scout(BIGINT, TEXT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.finalize_youth_scout_report(BIGINT, JSONB, TEXT) TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.sign_youth_scout_prospect(BIGINT, UUID, INTEGER) TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.player_cards.in_academy'),
            ('column:public.player_cards.academy_progress'),
            ('column:public.player_cards.academy_seated_at'),
            ('column:public.players.scouting_finishes_at'),
            ('column:public.players.scouting_active_tier'),
            ('table:public.scouting_reports'),
            ('policy:public.scouting_reports.scouting_reports_select'),
            ('policy:public.scouting_reports.scouting_reports_insert'),
            ('policy:public.scouting_reports.scouting_reports_update'),
            ('function:academy_slot_cap'),
            ('function:process_youth_intake'),
            ('function:promote_academy_player'),
            ('function:release_academy_player'),
            ('function:process_daily_academy_growth'),
            ('function:dispatch_youth_scout'),
            ('function:finalize_youth_scout_report'),
            ('function:sign_youth_scout_prospect')
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
                WHEN 'academy_slot_cap' THEN to_regprocedure('public.academy_slot_cap(integer)')
                WHEN 'process_youth_intake' THEN to_regprocedure('public.process_youth_intake(bigint,jsonb)')
                WHEN 'promote_academy_player' THEN to_regprocedure('public.promote_academy_player(bigint,uuid)')
                WHEN 'release_academy_player' THEN to_regprocedure('public.release_academy_player(bigint,uuid)')
                WHEN 'process_daily_academy_growth' THEN to_regprocedure('public.process_daily_academy_growth()')
                WHEN 'dispatch_youth_scout' THEN to_regprocedure('public.dispatch_youth_scout(bigint,text)')
                WHEN 'finalize_youth_scout_report' THEN to_regprocedure('public.finalize_youth_scout_report(bigint,jsonb,text)')
                WHEN 'sign_youth_scout_prospect' THEN to_regprocedure('public.sign_youth_scout_prospect(bigint,uuid,integer)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

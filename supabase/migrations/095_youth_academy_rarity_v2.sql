-- 095_youth_academy_rarity_v2.sql
-- Youth Academy V2: rarity ceilings, capacity 3/3/4/4/5, scout ranges, weekly ledger, aging.
-- US-42.2 / US-42.7 / US-42.9 — extends 015 + 049.

BEGIN;

-- ---------------------------------------------------------------------------
-- Columns on player_cards
-- ---------------------------------------------------------------------------
ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS pot_visible_lo INTEGER,
    ADD COLUMN IF NOT EXISTS pot_visible_hi INTEGER,
    ADD COLUMN IF NOT EXISTS scout_assessment_level TEXT NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS academy_origin TEXT,
    ADD COLUMN IF NOT EXISTS academy_age_out_pending_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS academy_warned_aging_at TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- Weekly actions ledger
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.academy_weekly_actions (
    owner_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    promotes_used INTEGER NOT NULL DEFAULT 0,
    paid_signings_used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (owner_id, week_start)
);

ALTER TABLE public.academy_weekly_actions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS academy_weekly_actions_select ON public.academy_weekly_actions;
CREATE POLICY academy_weekly_actions_select ON public.academy_weekly_actions
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS academy_weekly_actions_insert ON public.academy_weekly_actions;
CREATE POLICY academy_weekly_actions_insert ON public.academy_weekly_actions
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

DROP POLICY IF EXISTS academy_weekly_actions_update ON public.academy_weekly_actions;
CREATE POLICY academy_weekly_actions_update ON public.academy_weekly_actions
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- Per-prospect assessment jobs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.academy_scout_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    card_id UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    tier TEXT NOT NULL CHECK (tier IN ('quick', 'standard', 'deep')),
    finishes_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_academy_scout_assessments_pending_card
    ON public.academy_scout_assessments (card_id)
    WHERE status = 'pending';

ALTER TABLE public.academy_scout_assessments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS academy_scout_assessments_select ON public.academy_scout_assessments;
CREATE POLICY academy_scout_assessments_select ON public.academy_scout_assessments
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS academy_scout_assessments_insert ON public.academy_scout_assessments;
CREATE POLICY academy_scout_assessments_insert ON public.academy_scout_assessments
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

DROP POLICY IF EXISTS academy_scout_assessments_update ON public.academy_scout_assessments;
CREATE POLICY academy_scout_assessments_update ON public.academy_scout_assessments
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- game_config
-- ---------------------------------------------------------------------------
INSERT INTO public.game_config (key, value_json) VALUES
    ('youth_intake_count', '2'),
    ('youth_academy_v2_enabled', 'true'),
    ('youth_academy_legendary_enabled', 'true'),
    ('academy_weekly_promote_cap', '2'),
    ('academy_weekly_paid_sign_cap', '2'),
    ('academy_promote_fee', '500'),
    ('academy_promote_first_free', 'true'),
    ('academy_age_warn', '20'),
    ('academy_age_out', '21'),
    ('academy_age_out_grace_hours', '72'),
    ('academy_aging_decay_max', '1'),
    ('academy_initial_range_width', '[12,10,8,6,5]'),
    ('scout_deep_min_range', '2'),
    ('scout_narrow_quick', '2'),
    ('scout_narrow_standard', '3'),
    ('scout_narrow_deep', '4'),
    ('youth_academy_generation_version', '2')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

UPDATE public.game_config SET value_json = '2' WHERE key = 'youth_intake_count';
UPDATE public.game_config SET value_json = '21' WHERE key = 'academy_age_out';

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.academy_slot_cap(p_level INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE GREATEST(1, LEAST(5, COALESCE(p_level, 1)))
        WHEN 1 THEN 3
        WHEN 2 THEN 3
        WHEN 3 THEN 4
        WHEN 4 THEN 4
        ELSE 5
    END;
$$;

CREATE OR REPLACE FUNCTION public.academy_range_width_for_level(p_level INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_arr JSONB;
    v_level INTEGER := GREATEST(1, LEAST(5, COALESCE(p_level, 1)));
BEGIN
    v_arr := public.get_game_config('academy_initial_range_width');
    IF v_arr IS NULL OR jsonb_typeof(v_arr) <> 'array' THEN
        RETURN CASE v_level WHEN 1 THEN 12 WHEN 2 THEN 10 WHEN 3 THEN 8 WHEN 4 THEN 6 ELSE 5 END;
    END IF;
    RETURN GREATEST(1, COALESCE((v_arr ->> (v_level - 1))::INTEGER, 8));
END;
$$;

CREATE OR REPLACE FUNCTION public.academy_init_visible_range(
    p_potential INTEGER,
    p_rarity TEXT,
    p_level INTEGER,
    OUT o_lo INTEGER,
    OUT o_hi INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cap INTEGER;
    v_pot INTEGER;
    v_w INTEGER;
    v_half INTEGER;
BEGIN
    v_cap := public.rarity_potential_cap(p_rarity);
    IF v_cap IS NULL THEN
        RAISE EXCEPTION 'Unsupported rarity %', p_rarity;
    END IF;
    v_pot := GREATEST(1, LEAST(COALESCE(p_potential, 1), v_cap));
    v_w := public.academy_range_width_for_level(p_level);
    v_half := v_w / 2;
    o_lo := GREATEST(1, v_pot - v_half);
    o_hi := LEAST(v_cap, v_pot + (v_w - 1 - v_half));
    o_lo := LEAST(o_lo, v_pot);
    o_hi := GREATEST(o_hi, v_pot);
END;
$$;

CREATE OR REPLACE FUNCTION public.academy_narrow_visible_range(
    p_lo INTEGER,
    p_hi INTEGER,
    p_potential INTEGER,
    p_rarity TEXT,
    p_tier TEXT,
    OUT o_lo INTEGER,
    OUT o_hi INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cap INTEGER;
    v_pot INTEGER;
    v_trim INTEGER;
    v_tier TEXT := lower(trim(p_tier));
    v_min_w INTEGER;
    v_cur_lo INTEGER;
    v_cur_hi INTEGER;
BEGIN
    v_cap := public.rarity_potential_cap(p_rarity);
    v_pot := GREATEST(1, LEAST(COALESCE(p_potential, 1), v_cap));
    v_cur_lo := GREATEST(1, LEAST(COALESCE(p_lo, v_pot), v_pot, v_cap));
    v_cur_hi := LEAST(v_cap, GREATEST(COALESCE(p_hi, v_pot), v_pot));
    IF v_tier = 'quick' THEN
        v_trim := public.get_game_config_int('scout_narrow_quick', 2)::INTEGER;
    ELSIF v_tier = 'standard' THEN
        v_trim := public.get_game_config_int('scout_narrow_standard', 3)::INTEGER;
    ELSIF v_tier = 'deep' THEN
        v_trim := public.get_game_config_int('scout_narrow_deep', 4)::INTEGER;
    ELSE
        RAISE EXCEPTION 'Invalid assessment tier';
    END IF;
    o_lo := GREATEST(v_cur_lo, LEAST(v_pot, v_cur_lo + v_trim));
    o_hi := LEAST(v_cur_hi, GREATEST(v_pot, v_cur_hi - v_trim));
    o_lo := LEAST(o_lo, v_pot);
    o_hi := GREATEST(o_hi, v_pot);
    -- Fog floor for all tiers (FR-010) — never collapse to exact POT by default
    v_min_w := public.get_game_config_int('scout_deep_min_range', 2)::INTEGER;
    WHILE (o_hi - o_lo + 1) < v_min_w AND (o_lo > v_cur_lo OR o_hi < v_cur_hi) LOOP
        IF o_lo > v_cur_lo AND (o_hi - o_lo + 1) < v_min_w THEN
            o_lo := o_lo - 1;
        END IF;
        IF o_hi < v_cur_hi AND (o_hi - o_lo + 1) < v_min_w THEN
            o_hi := o_hi + 1;
        END IF;
    END LOOP;
    o_lo := LEAST(o_lo, v_pot);
    o_hi := GREATEST(o_hi, v_pot);
END;
$$;

CREATE OR REPLACE FUNCTION public.ensure_academy_weekly_row(p_owner_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_week DATE := public.current_intake_week();
    v_row public.academy_weekly_actions;
BEGIN
    INSERT INTO public.academy_weekly_actions (owner_id, week_start)
    VALUES (p_owner_id, v_week)
    ON CONFLICT (owner_id, week_start) DO NOTHING;

    SELECT * INTO v_row
    FROM public.academy_weekly_actions
    WHERE owner_id = p_owner_id AND week_start = v_week
    FOR UPDATE;

    RETURN jsonb_build_object(
        'owner_id', v_row.owner_id,
        'week_start', v_row.week_start,
        'promotes_used', v_row.promotes_used,
        'paid_signings_used', v_row.paid_signings_used
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.academy_legendary_allowed(p_level INTEGER)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_enabled BOOLEAN;
BEGIN
    IF COALESCE(p_level, 1) < 5 THEN
        RETURN FALSE;
    END IF;
    BEGIN
        v_enabled := COALESCE((public.get_game_config('youth_academy_legendary_enabled') #>> '{}')::BOOLEAN, TRUE);
    EXCEPTION WHEN OTHERS THEN
        v_enabled := TRUE;
    END;
    RETURN v_enabled;
END;
$$;

-- ---------------------------------------------------------------------------
-- process_youth_intake
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_youth_intake(p_owner_id bigint, p_cards jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
    v_lo INTEGER;
    v_hi INTEGER;
    v_rarity TEXT;
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

    SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
    v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.player_cards
    WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;

    IF v_existing IS NOT NULL THEN
        RETURN jsonb_build_object(
            'owner_id', p_owner_id,
            'intake_week', v_week,
            'card_ids', to_jsonb(v_existing),
            'seated', COALESCE(array_length(v_existing, 1), 0),
            'skipped', 0,
            'slots_used', COALESCE(v_used, 0),
            'slots_cap', v_cap,
            'capacity_blocked', FALSE,
            'already_processed', TRUE
        );
    END IF;

    v_count := public.get_game_config_int('youth_intake_count', 2)::INTEGER;
    IF jsonb_array_length(p_cards) > v_count THEN
        RAISE EXCEPTION 'Intake exceeds max cards (%)', v_count;
    END IF;

    v_free := GREATEST(0, v_cap - COALESCE(v_used, 0));

    IF v_free <= 0 THEN
        INSERT INTO public.youth_intake_log (owner_id, intake_week, card_ids)
        VALUES (p_owner_id, v_week, ARRAY[]::UUID[]);
        RETURN jsonb_build_object(
            'owner_id', p_owner_id,
            'intake_week', v_week,
            'card_ids', '[]'::jsonb,
            'seated', 0,
            'skipped', jsonb_array_length(p_cards),
            'slots_used', COALESCE(v_used, 0),
            'slots_cap', v_cap,
            'capacity_blocked', TRUE,
            'already_processed', FALSE
        );
    END IF;

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

        v_rarity := COALESCE(NULLIF(trim(v_card.rarity), ''), 'Common');
        IF v_rarity = 'Legendary' AND NOT public.academy_legendary_allowed(COALESCE(v_level, 1)) THEN
            RAISE EXCEPTION 'Legendary academy prospects require YA level 5 with Legendary enabled';
        END IF;

        v_pot := COALESCE(v_card.potential, v_card.base_potential);
        IF v_pot IS NULL THEN
            RAISE EXCEPTION 'Card % missing potential', v_card.name;
        END IF;
        PERFORM public.assert_card_potential_integrity(
            v_rarity,
            v_card.overall,
            v_pot,
            COALESCE(v_card.base_potential, v_pot)
        );

        SELECT o_lo, o_hi INTO v_lo, v_hi
        FROM public.academy_init_visible_range(v_pot, v_rarity, COALESCE(v_level, 1));

        v_dob := COALESCE(
            v_card.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card.age, 18) || ' years')::INTERVAL)::DATE
        );

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
            in_academy, academy_progress, academy_seated_at,
            pot_visible_lo, pot_visible_hi, scout_assessment_level, academy_origin
        ) VALUES (
            p_owner_id, v_card.name, v_card.position, v_rarity,
            v_card.base_rating, 1, v_card.overall,
            COALESCE(v_card.pac, 50), COALESCE(v_card.sho, 50),
            COALESCE(v_card.pas, 50), COALESCE(v_card.dri, 50),
            COALESCE(v_card.def, 50), COALESCE(v_card.phy, 50),
            v_pot,
            COALESCE(v_card.base_potential, v_pot),
            public.card_age_from_dob(v_dob),
            v_dob,
            COALESCE(NULLIF(trim(v_card.role), ''), 'Balanced'),
            TRUE, 0, NOW(),
            v_lo, v_hi, 'none', 'weekly_intake'
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
        'capacity_blocked', FALSE,
        'already_processed', FALSE
    );
END;
$function$;

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
    v_week public.academy_weekly_actions;
    v_promote_cap INTEGER;
    v_fee BIGINT;
    v_first_free BOOLEAN;
    v_days INTEGER;
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

    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'academy_promote');

    PERFORM public.ensure_academy_weekly_row(p_owner_id);
    SELECT * INTO v_week
    FROM public.academy_weekly_actions
    WHERE owner_id = p_owner_id AND week_start = public.current_intake_week()
    FOR UPDATE;
    v_promote_cap := public.get_game_config_int('academy_weekly_promote_cap', 2)::INTEGER;
    IF v_week.promotes_used >= v_promote_cap THEN
        RAISE EXCEPTION 'Weekly academy promotion limit reached (%/%). Try again next week.',
            v_week.promotes_used, v_promote_cap;
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

    BEGIN
        v_first_free := COALESCE((public.get_game_config('academy_promote_first_free') #>> '{}')::BOOLEAN, TRUE);
    EXCEPTION WHEN OTHERS THEN
        v_first_free := TRUE;
    END;
    v_fee := public.get_game_config_int('academy_promote_fee', 500);
    IF v_first_free AND v_week.promotes_used = 0 THEN
        v_fee := 0;
    END IF;
    IF v_fee > 0 THEN
        PERFORM public.apply_club_economy(
            p_owner_id,
            -v_fee,
            0,
            'academy_promote',
            'academy_promote:' || p_owner_id::TEXT || ':' || p_card_id::TEXT || ':' || v_week.week_start::TEXT,
            jsonb_build_object('card_id', p_card_id)
        );
    END IF;

    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;

    UPDATE public.player_cards
    SET in_academy = FALSE,
        academy_progress = 0,
        academy_seated_at = NULL,
        academy_age_out_pending_at = NULL,
        academy_warned_aging_at = NULL
    WHERE id = p_card_id;

    UPDATE public.academy_weekly_actions
    SET promotes_used = promotes_used + 1
    WHERE owner_id = p_owner_id AND week_start = v_week.week_start;

    UPDATE public.academy_scout_assessments
    SET status = 'cancelled'
    WHERE card_id = p_card_id AND status = 'pending';

    v_ready := public.get_game_config_int('academy_ready_ovr', 65)::INTEGER;
    v_ovr := v_card.overall;
    v_days := GREATEST(0, EXTRACT(DAY FROM (NOW() - COALESCE(v_card.academy_seated_at, NOW())))::INTEGER);

    RETURN jsonb_build_object(
        'card_id', p_card_id,
        'name', v_card.name,
        'overall', v_ovr,
        'potential', v_card.potential,
        'rarity', v_card.rarity,
        'age', v_card.age,
        'days_developed', v_days,
        'fee', v_fee,
        'promotes_used', v_week.promotes_used + 1,
        'promote_cap', v_promote_cap,
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

    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'academy_release');

    UPDATE public.academy_scout_assessments
    SET status = 'cancelled'
    WHERE card_id = p_card_id AND status = 'pending';

    DELETE FROM public.squad_assignments WHERE player_card_id = p_card_id;
    DELETE FROM public.player_cards WHERE id = p_card_id;

    RETURN jsonb_build_object(
        'released_card_id', p_card_id,
        'name', v_name
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- Discovery sign
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sign_youth_scout_prospect(p_owner_id bigint, p_report_id uuid, p_index integer)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_report RECORD;
    v_card JSONB;
    v_level INTEGER;
    v_cap INTEGER;
    v_used INTEGER;
    v_dob DATE;
    v_pot INT;
    v_card_id UUID;
    v_week public.academy_weekly_actions;
    v_sign_cap INTEGER;
    v_lo INTEGER;
    v_hi INTEGER;
    v_rarity TEXT;
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

    PERFORM public.ensure_academy_weekly_row(p_owner_id);
    SELECT * INTO v_week
    FROM public.academy_weekly_actions
    WHERE owner_id = p_owner_id AND week_start = public.current_intake_week()
    FOR UPDATE;
    v_sign_cap := public.get_game_config_int('academy_weekly_paid_sign_cap', 2)::INTEGER;
    IF v_week.paid_signings_used >= v_sign_cap THEN
        RAISE EXCEPTION 'Weekly paid academy signing limit reached (%/%).',
            v_week.paid_signings_used, v_sign_cap;
    END IF;

    SELECT youth_academy_level INTO v_level FROM public.players WHERE discord_id = p_owner_id;
    v_cap := public.academy_slot_cap(COALESCE(v_level, 1));
    SELECT COUNT(*)::INTEGER INTO v_used
    FROM public.player_cards
    WHERE owner_id = p_owner_id AND in_academy = TRUE AND COALESCE(is_retired, FALSE) = FALSE;
    IF COALESCE(v_used, 0) >= v_cap THEN
        RAISE EXCEPTION 'Academy slots full (%/%). Promote or release first.', v_used, v_cap;
    END IF;

    v_card := v_report.prospects_json -> p_index;
    IF v_card IS NULL OR jsonb_typeof(v_card) <> 'object' THEN
        RAISE EXCEPTION 'Prospect missing';
    END IF;

    v_rarity := COALESCE(v_card->>'rarity', 'Common');
    IF v_rarity = 'Legendary' AND NOT public.academy_legendary_allowed(COALESCE(v_level, 1)) THEN
        RAISE EXCEPTION 'Legendary academy prospects require YA level 5 with Legendary enabled';
    END IF;

    v_pot := COALESCE((v_card->>'potential')::INT, (v_card->>'base_potential')::INT);
    IF v_pot IS NULL THEN
        RAISE EXCEPTION 'Prospect missing potential';
    END IF;
    PERFORM public.assert_card_potential_integrity(
        v_rarity,
        COALESCE((v_card->>'overall')::INT, 0),
        v_pot,
        COALESCE((v_card->>'base_potential')::INT, v_pot)
    );

    SELECT o_lo, o_hi INTO v_lo, v_hi
    FROM public.academy_init_visible_range(v_pot, v_rarity, COALESCE(v_level, 1));

    v_dob := COALESCE(
        NULLIF(v_card->>'date_of_birth', '')::DATE,
        (CURRENT_DATE - (COALESCE((v_card->>'age')::INT, 18) || ' years')::INTERVAL)::DATE
    );

    INSERT INTO public.player_cards (
        owner_id, name, position, rarity, base_rating, level, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
        in_academy, academy_progress, academy_seated_at,
        pot_visible_lo, pot_visible_hi, scout_assessment_level, academy_origin
    ) VALUES (
        p_owner_id,
        v_card->>'name',
        v_card->>'position',
        v_rarity,
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
        TRUE, 0, NOW(),
        v_lo, v_hi, 'none', 'paid_scout'
    ) RETURNING id INTO v_card_id;

    UPDATE public.scouting_reports
    SET signed_card_id = v_card_id
    WHERE id = p_report_id;

    UPDATE public.academy_weekly_actions
    SET paid_signings_used = paid_signings_used + 1
    WHERE owner_id = p_owner_id AND week_start = v_week.week_start;

    PERFORM public.ensure_card_ownership_open(v_card_id, p_owner_id, 'youth_scout');

    RETURN jsonb_build_object(
        'card_id', v_card_id,
        'report_id', p_report_id,
        'index', p_index,
        'paid_signings_used', v_week.paid_signings_used + 1,
        'sign_cap', v_sign_cap
    );
END;
$function$;

-- ---------------------------------------------------------------------------
-- Assessment scout
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.dispatch_academy_assessment(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_tier TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_tier TEXT := lower(trim(p_tier));
    v_card RECORD;
    v_cost BIGINT;
    v_hours INTEGER;
    v_finishes TIMESTAMPTZ;
    v_eco JSONB;
    v_id UUID;
BEGIN
    IF v_tier NOT IN ('quick', 'standard', 'deep') THEN
        RAISE EXCEPTION 'Invalid assessment tier';
    END IF;

    SELECT * INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id AND in_academy = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Not an academy player';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.academy_scout_assessments
        WHERE card_id = p_card_id AND status = 'pending'
    ) THEN
        RAISE EXCEPTION 'Assessment already in progress for this prospect';
    END IF;

    v_cost := public.get_game_config_int('scout_cost_' || v_tier, 3000);
    v_hours := public.get_game_config_int('scout_hours_' || v_tier, 2)::INTEGER;
    v_finishes := NOW() + make_interval(hours => v_hours);

    v_eco := public.apply_club_economy(
        p_owner_id,
        -v_cost,
        0,
        'academy_assess_' || v_tier,
        'academy_assess:' || p_owner_id::TEXT || ':' || p_card_id::TEXT || ':' || v_tier || ':' || v_finishes::TEXT,
        jsonb_build_object('card_id', p_card_id, 'tier', v_tier)
    );

    INSERT INTO public.academy_scout_assessments (owner_id, card_id, tier, finishes_at, status)
    VALUES (p_owner_id, p_card_id, v_tier, v_finishes, 'pending')
    RETURNING id INTO v_id;

    RETURN jsonb_build_object(
        'assessment_id', v_id,
        'card_id', p_card_id,
        'tier', v_tier,
        'finishes_at', v_finishes,
        'cost', v_cost,
        'economy', v_eco
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.finalize_academy_assessment(
    p_owner_id BIGINT,
    p_card_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_job RECORD;
    v_card RECORD;
    v_lo INTEGER;
    v_hi INTEGER;
    v_level TEXT;
BEGIN
    SELECT * INTO v_job
    FROM public.academy_scout_assessments
    WHERE owner_id = p_owner_id AND card_id = p_card_id AND status = 'pending'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No pending assessment for this prospect';
    END IF;
    IF v_job.finishes_at > NOW() THEN
        RAISE EXCEPTION 'Assessment not finished yet';
    END IF;

    SELECT * INTO v_card
    FROM public.player_cards
    WHERE id = p_card_id AND owner_id = p_owner_id AND in_academy = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        UPDATE public.academy_scout_assessments SET status = 'cancelled' WHERE id = v_job.id;
        RAISE EXCEPTION 'Prospect no longer in academy';
    END IF;

    SELECT o_lo, o_hi INTO v_lo, v_hi
    FROM public.academy_narrow_visible_range(
        COALESCE(v_card.pot_visible_lo, v_card.potential),
        COALESCE(v_card.pot_visible_hi, v_card.potential),
        v_card.potential,
        v_card.rarity,
        v_job.tier
    );

    v_level := CASE
        WHEN COALESCE(v_card.scout_assessment_level, 'none') = 'deep' THEN 'deep'
        WHEN v_job.tier = 'deep' THEN 'deep'
        WHEN COALESCE(v_card.scout_assessment_level, 'none') = 'standard' OR v_job.tier = 'standard' THEN 'standard'
        WHEN COALESCE(v_card.scout_assessment_level, 'none') = 'quick' OR v_job.tier = 'quick' THEN 'quick'
        ELSE 'none'
    END;

    UPDATE public.player_cards
    SET pot_visible_lo = v_lo,
        pot_visible_hi = v_hi,
        scout_assessment_level = v_level
    WHERE id = p_card_id;

    UPDATE public.academy_scout_assessments
    SET status = 'completed'
    WHERE id = v_job.id;

    RETURN jsonb_build_object(
        'card_id', p_card_id,
        'tier', v_job.tier,
        'pot_visible_lo', v_lo,
        'pot_visible_hi', v_hi,
        'scout_assessment_level', v_level
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.finalize_due_academy_assessments()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_row RECORD;
    v_n INTEGER := 0;
    v_res JSONB;
BEGIN
    FOR v_row IN
        SELECT owner_id, card_id
        FROM public.academy_scout_assessments
        WHERE status = 'pending' AND finishes_at <= NOW()
    LOOP
        BEGIN
            v_res := public.finalize_academy_assessment(v_row.owner_id, v_row.card_id);
            v_n := v_n + 1;
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END LOOP;
    RETURN jsonb_build_object('finalized', v_n);
END;
$$;

-- ---------------------------------------------------------------------------
-- Daily growth + aging (no force-promote)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.process_daily_academy_growth()
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
    v_age_warn INTEGER;
    v_grace_hours INTEGER;
    v_ready INTEGER;
    v_ticked INTEGER := 0;
    v_warned JSONB := '[]'::JSONB;
    v_released JSONB := '[]'::JSONB;
BEGIN
    v_age_out := public.get_game_config_int('academy_age_out', 21)::INTEGER;
    v_age_warn := public.get_game_config_int('academy_age_warn', 20)::INTEGER;
    v_grace_hours := public.get_game_config_int('academy_age_out_grace_hours', 72)::INTEGER;
    v_ready := public.get_game_config_int('academy_ready_ovr', 65)::INTEGER;

    PERFORM public.finalize_due_academy_assessments();

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
        v_pot := public.effective_card_potential(
            v_card.rarity,
            GREATEST(v_card.overall, COALESCE(v_card.potential, v_card.overall))
        );
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

        v_age := public.card_age_from_dob(v_card.date_of_birth);

        UPDATE public.player_cards
        SET overall = v_ovr,
            academy_progress = v_prog,
            pac = v_card.pac,
            sho = v_card.sho,
            pas = v_card.pas,
            dri = v_card.dri,
            "def" = v_card."def",
            phy = v_card.phy,
            age = v_age,
            academy_warned_aging_at = CASE
                WHEN v_age >= v_age_warn AND academy_warned_aging_at IS NULL THEN NOW()
                ELSE academy_warned_aging_at
            END,
            academy_age_out_pending_at = CASE
                WHEN v_age >= v_age_out AND academy_age_out_pending_at IS NULL THEN NOW()
                ELSE academy_age_out_pending_at
            END
        WHERE id = v_card.id;

        v_ticked := v_ticked + 1;

        IF v_age >= v_age_warn AND v_card.academy_warned_aging_at IS NULL THEN
            v_warned := v_warned || jsonb_build_array(jsonb_build_object(
                'owner_id', v_card.owner_id,
                'card_id', v_card.id,
                'name', v_card.name,
                'age', v_age
            ));
        END IF;

        -- Auto-release after grace (not force-promote)
        IF COALESCE(v_card.academy_age_out_pending_at, CASE WHEN v_age >= v_age_out THEN NOW() ELSE NULL END) IS NOT NULL
           AND (
                COALESCE(v_card.academy_age_out_pending_at, NOW())
                + make_interval(hours => v_grace_hours)
           ) <= NOW()
        THEN
            BEGIN
                PERFORM public.release_academy_player(v_card.owner_id, v_card.id);
                v_released := v_released || jsonb_build_array(jsonb_build_object(
                    'owner_id', v_card.owner_id,
                    'card_id', v_card.id,
                    'name', v_card.name,
                    'result', 'auto_released',
                    'reason', 'age_out_grace'
                ));
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'ticked', v_ticked,
        'aging_warned', v_warned,
        'age_out_released', v_released,
        'ready_ovr', v_ready
    );
END;
$function$;

-- ---------------------------------------------------------------------------
-- Cutover: repair + init ranges (academy seats only)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_cap INTEGER;
    v_lo INTEGER;
    v_hi INTEGER;
    v_row RECORD;
    v_level INTEGER;
BEGIN
    FOR v_row IN
        SELECT pc.id, pc.rarity, pc.overall, pc.potential, pc.base_potential, pc.owner_id,
               COALESCE(p.youth_academy_level, 1) AS ya_level
        FROM public.player_cards pc
        LEFT JOIN public.players p ON p.discord_id = pc.owner_id
        WHERE pc.in_academy = TRUE
          AND COALESCE(pc.is_retired, FALSE) = FALSE
    LOOP
        v_cap := public.rarity_potential_cap(v_row.rarity);
        IF v_cap IS NULL THEN
            CONTINUE;
        END IF;
        -- Repair POT when OVR is legal; leave OVR > cap for global 049 handling
        IF v_row.overall <= v_cap AND (v_row.potential > v_cap OR COALESCE(v_row.base_potential, v_row.potential) > v_cap) THEN
            UPDATE public.player_cards
            SET potential = GREATEST(overall, LEAST(potential, v_cap)),
                base_potential = GREATEST(overall, LEAST(COALESCE(base_potential, potential), v_cap))
            WHERE id = v_row.id;
        END IF;

        SELECT potential, rarity INTO v_row.potential, v_row.rarity
        FROM public.player_cards WHERE id = v_row.id;

        v_level := v_row.ya_level;
        SELECT o_lo, o_hi INTO v_lo, v_hi
        FROM public.academy_init_visible_range(
            (SELECT potential FROM public.player_cards WHERE id = v_row.id),
            (SELECT rarity FROM public.player_cards WHERE id = v_row.id),
            v_level
        );

        UPDATE public.player_cards
        SET pot_visible_lo = COALESCE(pot_visible_lo, v_lo),
            pot_visible_hi = COALESCE(pot_visible_hi, v_hi),
            academy_origin = COALESCE(academy_origin, 'migration'),
            scout_assessment_level = COALESCE(NULLIF(scout_assessment_level, ''), 'none')
        WHERE id = v_row.id
          AND (pot_visible_lo IS NULL OR pot_visible_hi IS NULL OR academy_origin IS NULL);
    END LOOP;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.academy_slot_cap(INTEGER)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.academy_init_visible_range(INTEGER, TEXT, INTEGER)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.academy_narrow_visible_range(INTEGER, INTEGER, INTEGER, TEXT, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.ensure_academy_weekly_row(BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.dispatch_academy_assessment(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.finalize_academy_assessment(BIGINT, UUID)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.finalize_due_academy_assessments()
    TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.academy_weekly_actions
    TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.academy_scout_assessments
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_missing TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'player_cards' AND column_name = 'pot_visible_lo'
    ) THEN
        RAISE EXCEPTION 'Migration 095 guard failed — missing pot_visible_lo';
    END IF;

    SELECT string_agg(req.obj, ', ')
    INTO v_missing
    FROM (
        VALUES
            ('table:public.academy_weekly_actions'),
            ('table:public.academy_scout_assessments'),
            ('function:dispatch_academy_assessment'),
            ('function:finalize_academy_assessment'),
            ('function:finalize_due_academy_assessments'),
            ('function:ensure_academy_weekly_row'),
            ('policy:public.academy_weekly_actions.academy_weekly_actions_select'),
            ('policy:public.academy_scout_assessments.academy_scout_assessments_select')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (req.obj = 'function:dispatch_academy_assessment'
            AND to_regprocedure('public.dispatch_academy_assessment(bigint,uuid,text)') IS NOT NULL)
        OR (req.obj = 'function:finalize_academy_assessment'
            AND to_regprocedure('public.finalize_academy_assessment(bigint,uuid)') IS NOT NULL)
        OR (req.obj = 'function:finalize_due_academy_assessments'
            AND to_regprocedure('public.finalize_due_academy_assessments()') IS NOT NULL)
        OR (req.obj = 'function:ensure_academy_weekly_row'
            AND to_regprocedure('public.ensure_academy_weekly_row(bigint)') IS NOT NULL)
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = 'public'
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(req.obj, '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 095 guard failed — missing: %', v_missing;
    END IF;
END;
$$;

COMMIT;

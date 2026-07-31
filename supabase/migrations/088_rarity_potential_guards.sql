-- 088_rarity_potential_guards.sql
-- US-42.2 / US-42.7 / US-42.9 — rarity potential cap integrity (049)
-- Containment only. VALIDATE constraints in 089 after repair.

CREATE OR REPLACE FUNCTION public.rarity_potential_cap(p_rarity TEXT)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT CASE p_rarity
        WHEN 'Common' THEN 75
        WHEN 'Rare' THEN 85
        WHEN 'Epic' THEN 92
        WHEN 'Legendary' THEN 99
        ELSE NULL
    END;
$$;

CREATE OR REPLACE FUNCTION public.effective_card_potential(p_rarity TEXT, p_potential INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT LEAST(p_potential, public.rarity_potential_cap(p_rarity));
$$;

CREATE OR REPLACE FUNCTION public.assert_card_potential_integrity(
    p_rarity TEXT,
    p_overall INTEGER,
    p_potential INTEGER,
    p_base_potential INTEGER
) RETURNS VOID
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_cap INTEGER := public.rarity_potential_cap(p_rarity);
BEGIN
    IF v_cap IS NULL THEN
        RAISE EXCEPTION 'Unsupported rarity: %', p_rarity;
    END IF;
    IF p_overall > v_cap THEN
        RAISE EXCEPTION 'OVR % exceeds rarity cap % for %', p_overall, v_cap, p_rarity;
    END IF;
    IF p_potential > v_cap THEN
        RAISE EXCEPTION 'POT % exceeds rarity cap % for %', p_potential, v_cap, p_rarity;
    END IF;
    IF p_base_potential IS NOT NULL AND p_base_potential > v_cap THEN
        RAISE EXCEPTION 'base POT % exceeds rarity cap % for %', p_base_potential, v_cap, p_rarity;
    END IF;
    IF p_overall > p_potential THEN
        RAISE EXCEPTION 'OVR % exceeds POT %', p_overall, p_potential;
    END IF;
END;
$$;

INSERT INTO public.game_config (key, value_json)
VALUES ('potential_rarity_caps_enabled', 'true'::jsonb)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.potential_cap_repair_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id TEXT NOT NULL,
    card_id UUID NOT NULL,
    owner_id BIGINT,
    rarity TEXT NOT NULL,
    old_overall INTEGER,
    new_overall INTEGER,
    old_potential INTEGER,
    new_potential INTEGER,
    old_base_potential INTEGER,
    new_base_potential INTEGER,
    old_stats JSONB,
    new_stats JSONB,
    refund_sp INTEGER NOT NULL DEFAULT 0,
    refund_coins BIGINT NOT NULL DEFAULT 0,
    refund_energy INTEGER NOT NULL DEFAULT 0,
    refund_other JSONB NOT NULL DEFAULT '{}'::jsonb,
    refund_confidence TEXT NOT NULL DEFAULT 'NONE'
        CHECK (refund_confidence IN ('EXACT', 'RECONSTRUCTED', 'MANUAL_REVIEW', 'NONE')),
    repair_category TEXT
        CHECK (repair_category IS NULL OR repair_category IN ('A', 'B', 'C')),
    repair_status TEXT NOT NULL DEFAULT 'dry_run',
    repaired_at TIMESTAMPTZ,
    notified_at TIMESTAMPTZ,
    notification_attempts INTEGER NOT NULL DEFAULT 0,
    notification_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, card_id)
);

CREATE INDEX IF NOT EXISTS idx_potential_cap_repair_audit_owner
    ON public.potential_cap_repair_audit (owner_id);

ALTER TABLE public.potential_cap_repair_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS potential_cap_repair_audit_select ON public.potential_cap_repair_audit;
CREATE POLICY potential_cap_repair_audit_select ON public.potential_cap_repair_audit
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS potential_cap_repair_audit_insert ON public.potential_cap_repair_audit;
CREATE POLICY potential_cap_repair_audit_insert ON public.potential_cap_repair_audit
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

DROP POLICY IF EXISTS potential_cap_repair_audit_update ON public.potential_cap_repair_audit;
CREATE POLICY potential_cap_repair_audit_update ON public.potential_cap_repair_audit
    FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.potential_cap_repair_audit
    TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.count_potential_integrity_anomalies()
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(*)::INTEGER
    FROM public.player_cards
    WHERE public.rarity_potential_cap(rarity) IS NULL
       OR potential > public.rarity_potential_cap(rarity)
       OR (
            base_potential IS NOT NULL
            AND base_potential > public.rarity_potential_cap(rarity)
       )
       OR overall > potential;
$$;

GRANT EXECUTE ON FUNCTION public.count_potential_integrity_anomalies()
    TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.process_match_result(p_result text, p_card_ids uuid[], p_xp_amount integer, p_card_ratings numeric[] DEFAULT NULL::numeric[], p_xp_amounts integer[] DEFAULT NULL::integer[], p_match_history_id uuid DEFAULT NULL::uuid)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
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
    v_rarity TEXT;
    v_xp INTEGER;
    v_dob DATE;
    v_xp_applied TIMESTAMPTZ;
BEGIN
    IF p_match_history_id IS NOT NULL THEN
        SELECT xp_applied_at INTO v_xp_applied
        FROM public.match_history
        WHERE id = p_match_history_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'match_history row not found';
        END IF;
        IF v_xp_applied IS NOT NULL THEN
            RETURN TRUE;
        END IF;
    END IF;

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

        SELECT date_of_birth, potential, base_potential, recent_match_ratings, rarity
        INTO v_dob, v_pot, v_init_pot, v_recent, v_rarity
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
                    v_new_pot := LEAST(
                        public.rarity_potential_cap(v_rarity),
                        v_pot + v_boost,
                        v_init_pot + 10
                    );
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

    IF p_match_history_id IS NOT NULL THEN
        UPDATE public.match_history
        SET xp_applied_at = NOW()
        WHERE id = p_match_history_id;
    END IF;

    RETURN TRUE;
END;
$function$;

CREATE OR REPLACE FUNCTION public.register_new_player(p_discord_id bigint, p_username text, p_club_name text, p_manager_name text, p_cards jsonb)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
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
        PERFORM public.assert_card_potential_integrity(
            v_card_record.rarity,
            v_card_record.overall,
            v_pot,
            COALESCE(v_card_record.base_potential, v_pot)
        );

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
$function$;

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
        PERFORM public.assert_card_potential_integrity(
            v_card.rarity,
            v_card.overall,
            v_pot,
            COALESCE(v_card.base_potential, v_pot)
        );

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
$function$;

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
    PERFORM public.assert_card_potential_integrity(
        COALESCE(v_card->>'rarity', 'Common'),
        COALESCE((v_card->>'overall')::INT, 0),
        v_pot,
        COALESCE((v_card->>'base_potential')::INT, v_pot)
    );

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
$function$;

CREATE OR REPLACE FUNCTION public.claim_daily_pack(p_club_id bigint, p_cards jsonb, p_topgg_vote_at timestamp with time zone, p_idempotency_key text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_last TIMESTAMPTZ;
    v_consumed TIMESTAMPTZ;
    v_now TIMESTAMPTZ := NOW();
    v_card RECORD;
    v_card_id UUID;
    v_ids UUID[] := ARRAY[]::UUID[];
    v_remaining INTEGER;
    v_dob DATE;
    v_cooldown_hours INTEGER;
    v_prior JSONB;
    v_result JSONB;
BEGIN
    IF p_idempotency_key IS NOT NULL THEN
        SELECT result_json INTO v_prior
        FROM public.pack_claim_runs
        WHERE idempotency_key = p_idempotency_key;

        IF FOUND THEN
            RETURN jsonb_build_object(
                'status', 'already_applied',
                'reason', NULL,
                'data', v_prior
            );
        END IF;
    END IF;

    IF p_cards IS NULL OR jsonb_array_length(p_cards) < 1 THEN
        RETURN jsonb_build_object(
            'status', 'rejected',
            'reason', 'empty_pack',
            'data', '{}'::JSONB
        );
    END IF;

    IF p_topgg_vote_at IS NULL THEN
        RAISE EXCEPTION 'VOTE_REQUIRED';
    END IF;

    IF p_topgg_vote_at < v_now - INTERVAL '12 hours' THEN
        RAISE EXCEPTION 'VOTE_STALE';
    END IF;

    v_cooldown_hours := public.get_game_config_int('daily_pack_cooldown_hours', 12)::INTEGER;

    SELECT last_claim_at, last_consumed_topgg_vote_at
    INTO v_last, v_consumed
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account not found';
    END IF;

    IF v_consumed IS NOT NULL AND p_topgg_vote_at <= v_consumed THEN
        RAISE EXCEPTION 'VOTE_ALREADY_USED';
    END IF;

    IF v_last IS NOT NULL AND v_now < v_last + (v_cooldown_hours || ' hours')::INTERVAL THEN
        v_remaining := EXTRACT(EPOCH FROM (v_last + (v_cooldown_hours || ' hours')::INTERVAL - v_now))::INTEGER;
        RAISE EXCEPTION 'COOLDOWN:%', v_remaining;
    END IF;

    UPDATE public.players
    SET last_claim_at = v_now,
        last_consumed_topgg_vote_at = p_topgg_vote_at
    WHERE discord_id = p_club_id;

    FOR v_card IN
        SELECT * FROM jsonb_to_recordset(p_cards) AS x(
            name TEXT, position TEXT, rarity TEXT, base_rating INT, overall INT,
            pac INT, sho INT, pas INT, dri INT, "def" INT, phy INT,
            potential INT, base_potential INT, age INT, date_of_birth DATE, role TEXT
        )
    LOOP
        v_dob := COALESCE(
            v_card.date_of_birth,
            (CURRENT_DATE - (COALESCE(v_card.age, 25) || ' years')::INTERVAL)::DATE
        );

        PERFORM public.assert_card_potential_integrity(
            v_card.rarity,
            v_card.overall,
            COALESCE(v_card.potential, v_card.base_potential, v_card.overall),
            COALESCE(v_card.base_potential, v_card.potential, v_card.overall)
        );

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
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
            v_dob,
            COALESCE(NULLIF(trim(v_card.role), ''), 'Balanced')
        )
        RETURNING id INTO v_card_id;

        v_ids := array_append(v_ids, v_card_id);
    END LOOP;

    v_result := jsonb_build_object(
        'card_ids', to_jsonb(v_ids),
        'claimed_at', to_jsonb(v_now),
        'vote_consumed_at', to_jsonb(p_topgg_vote_at)
    );

    IF p_idempotency_key IS NOT NULL THEN
        BEGIN
            INSERT INTO public.pack_claim_runs (idempotency_key, club_id, result_json)
            VALUES (p_idempotency_key, p_club_id, v_result);
        EXCEPTION
            WHEN unique_violation THEN
                SELECT result_json INTO v_prior
                FROM public.pack_claim_runs
                WHERE idempotency_key = p_idempotency_key;
                RETURN jsonb_build_object(
                    'status', 'already_applied',
                    'reason', NULL,
                    'data', COALESCE(v_prior, v_result)
                );
        END;
    END IF;

    RETURN jsonb_build_object(
        'status', 'applied',
        'reason', NULL,
        'data', v_result
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.allocate_skill_point(p_owner_id bigint, p_card_id uuid, p_stat text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_col TEXT;
    v_points INTEGER;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_overall INTEGER;
    v_potential INTEGER;
    v_rarity TEXT;
    v_alloc_count INTEGER;
    v_alloc_reset DATE;
    v_alloc_cap CONSTANT INTEGER := 15;
    v_pacing_until CONSTANT DATE := DATE '2026-08-06';
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);
    PERFORM public.assert_card_not_on_transfer_list(p_card_id);
    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'allocate');

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
        'SELECT skill_points, overall, potential, rarity, %I, daily_alloc_count, alloc_reset_date '
        || 'FROM public.player_cards WHERE id = $1 AND owner_id = $2 FOR UPDATE',
        v_col
    ) INTO v_points, v_overall, v_potential, v_rarity, v_current, v_alloc_count, v_alloc_reset
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
    v_potential := public.effective_card_potential(v_rarity, v_potential);

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
$function$;

CREATE OR REPLACE FUNCTION public.process_stat_drill(p_owner_id bigint, p_card_id uuid, p_drill_id text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
    v_stat_col TEXT;
    v_stat_val INTEGER;
    v_potential INTEGER;
    v_rarity TEXT;
    v_boost_eligible BOOLEAN := FALSE;
    v_stat_boosted BOOLEAN := FALSE;
    v_stat_delta INTEGER := 0;
    v_new_stat_value INTEGER := NULL;
    v_new_ovr INTEGER;
    v_boost_block_reason TEXT := NULL;
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
    PERFORM public.assert_card_action_allowed(p_owner_id, p_card_id, 'drill');

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

    v_stat_col := CASE p_drill_id
        WHEN 'pac_sprint' THEN 'pac'
        WHEN 'sho_finishing' THEN 'sho'
        WHEN 'pas_distribution' THEN 'pas'
        WHEN 'dri_dribble' THEN 'dri'
        WHEN 'def_tackling' THEN 'def'
        WHEN 'phy_strength' THEN 'phy'
    END;

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

    EXECUTE format(
        'SELECT overall, level, date_of_birth, potential, rarity, %I '
        || 'FROM public.player_cards WHERE id = $1 FOR UPDATE',
        v_stat_col
    ) INTO v_ovr, v_card_level, v_dob, v_potential, v_rarity, v_stat_val
    USING p_card_id;

    v_age := public.card_age_from_dob(v_dob);
    v_new_ovr := v_ovr;

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

    v_potential := public.effective_card_potential(v_rarity, v_potential);

    -- Soft-fail boost eligibility (do not RAISE — XP/costs still apply)
    IF v_stat_val >= 99 THEN
        v_boost_block_reason := 'stat_at_maximum';
    ELSIF v_ovr >= v_potential THEN
        v_boost_block_reason := 'at_potential';
    ELSIF public.peek_card_ovr(p_card_id, v_stat_col, v_stat_val + 1) > v_potential THEN
        v_boost_block_reason := 'would_exceed_potential';
    ELSE
        v_boost_eligible := TRUE;
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

    IF v_boost_eligible THEN
        EXECUTE format(
            'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
            v_stat_col
        ) USING v_stat_val + 1, p_card_id;
        v_new_ovr := public.recalculate_card_ovr(p_card_id);
        v_stat_boosted := TRUE;
        v_stat_delta := 1;
        v_new_stat_value := v_stat_val + 1;
        v_boost_block_reason := NULL;
    END IF;

    v_xp_result := public.apply_card_xp(p_card_id, v_xp_gain, 'stat_drill_' || p_drill_id);

    RETURN jsonb_build_object(
        'xp_gain', v_xp_gain,
        'cost', v_cost,
        'daily_drill_count', v_daily + 1,
        'daily_drill_limit', v_daily_limit,
        'training_ground_bonus', public.training_ground_xp_bonus(v_tg_level),
        'economy', v_econ,
        'progression', v_xp_result,
        'stat_boosted', v_stat_boosted,
        'stat', upper(v_stat_col),
        'stat_delta', v_stat_delta,
        'new_stat_value', v_new_stat_value,
        'new_ovr', v_new_ovr,
        'boost_block_reason', v_boost_block_reason
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.claim_evolution_reward(p_owner_id bigint, p_evo_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_card_id UUID;
    v_evo_id TEXT;
    v_progress INTEGER;
    v_goal INTEGER;
    v_stat_col TEXT;
    v_reward_max INTEGER := 5;
    v_current INTEGER;
    v_new_val INTEGER;
    v_new_ovr INTEGER;
    v_applied INTEGER;
    v_status TEXT;
    v_overall INTEGER;
    v_potential INTEGER;
    v_rarity TEXT;
BEGIN
    PERFORM public.assert_not_in_match(p_owner_id);

    SELECT e.card_id, e.evolution_id,
           COALESCE(e.matches_played, e.current_progress),
           COALESCE(e.matches_required, e.target_goal),
           e.status
    INTO v_card_id, v_evo_id, v_progress, v_goal, v_status
    FROM public.active_evolutions e
    JOIN public.player_cards c ON c.id = e.card_id
    WHERE e.id = p_evo_id AND c.owner_id = p_owner_id
    FOR UPDATE;

    IF v_card_id IS NULL THEN
        RAISE EXCEPTION 'Evolution not found';
    END IF;
    PERFORM public.assert_card_action_allowed(p_owner_id, v_card_id, 'claim_evolution');
    IF v_status <> 'active' THEN
        RAISE EXCEPTION 'Evolution is not active';
    END IF;
    IF v_progress < v_goal THEN
        RAISE EXCEPTION 'Evolution not complete';
    END IF;

    SELECT overall, potential, rarity
    INTO v_overall, v_potential, v_rarity
    FROM public.player_cards
    WHERE id = v_card_id
    FOR UPDATE;

    v_potential := public.effective_card_potential(v_rarity, v_potential);

    v_stat_col := CASE v_evo_id
        WHEN 'pace_boost' THEN 'pac'
        WHEN 'shooting_star' THEN 'sho'
        WHEN 'def_wall' THEN 'def'
        ELSE 'pac'
    END;

    EXECUTE format(
        'SELECT %I FROM public.player_cards WHERE id = $1',
        v_stat_col
    ) INTO v_current USING v_card_id;

    v_applied := public.evolution_stat_reward_steps(v_card_id, v_stat_col, v_reward_max);
    v_new_val := v_current;
    IF v_applied > 0 THEN
        v_new_val := v_current + v_applied;
        EXECUTE format(
            'UPDATE public.player_cards SET %I = $1 WHERE id = $2',
            v_stat_col
        ) USING v_new_val, v_card_id;
    END IF;

    v_new_ovr := public.recalculate_card_ovr(v_card_id);

    UPDATE public.active_evolutions
    SET
        status = 'completed',
        rewards_applied = TRUE,
        completed_at = NOW()
    WHERE id = p_evo_id;

    RETURN jsonb_build_object(
        'new_ovr', v_new_ovr,
        'stat', upper(v_stat_col),
        'reward', v_applied,
        'reward_max', v_reward_max,
        'reward_clamped', (v_applied > 0 AND v_applied < v_reward_max),
        'blocked_by_cap', (v_applied = 0 AND v_overall >= v_potential AND v_current < 99)
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.evolution_stat_reward_steps(p_card_id uuid, p_stat_col text, p_max_steps integer DEFAULT 5)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_current INTEGER;
    v_overall INTEGER;
    v_potential INTEGER;
    v_rarity TEXT;
    v_steps INTEGER := 0;
    v_trial INTEGER;
    v_trial_ovr INTEGER;
BEGIN
    EXECUTE format(
        'SELECT %I, overall, potential, rarity FROM public.player_cards WHERE id = $1',
        p_stat_col
    ) INTO v_current, v_overall, v_potential, v_rarity USING p_card_id;

    IF v_current IS NULL THEN
        RETURN 0;
    END IF;
    v_potential := public.effective_card_potential(v_rarity, v_potential);
    IF v_overall >= v_potential OR v_current >= 99 THEN
        RETURN 0;
    END IF;

    FOR i IN 1..GREATEST(0, p_max_steps) LOOP
        EXIT WHEN v_current + v_steps >= 99;
        v_trial := v_current + v_steps + 1;
        v_trial_ovr := public.peek_card_ovr(p_card_id, p_stat_col, v_trial);
        IF v_trial_ovr > v_potential THEN
            EXIT;
        END IF;
        v_steps := v_steps + 1;
    END LOOP;

    RETURN v_steps;
END;
$function$;

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
$function$;

CREATE OR REPLACE FUNCTION public.train_with_fodder(p_owner_id bigint, p_target_id uuid, p_fodder_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_target_owner BIGINT;
    v_fodder_owner BIGINT;
    v_fodder_level INTEGER;
    v_fodder_overall INTEGER;
    v_target_overall INTEGER;
    v_target_potential INTEGER;
    v_target_rarity TEXT;
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
    PERFORM public.assert_card_action_allowed(p_owner_id, p_target_id, 'fusion');
    PERFORM public.assert_card_action_allowed(p_owner_id, p_fodder_id, 'fusion');
    PERFORM public.sync_action_energy(p_owner_id);

    v_fusion_cost := public.get_game_config_int('fusion_coins', 200);

    SELECT coins INTO v_coins
    FROM public.players
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF v_coins < v_fusion_cost THEN
        RAISE EXCEPTION 'Insufficient coins (% coins required for fusion)', v_fusion_cost;
    END IF;

    SELECT owner_id, overall, potential, rarity
    INTO v_target_owner, v_target_overall, v_target_potential, v_target_rarity
    FROM public.player_cards
    WHERE id = p_target_id
    FOR UPDATE;

    IF v_target_owner IS NULL OR v_target_owner != p_owner_id THEN
        RAISE EXCEPTION 'Target player card not found or not owned by you';
    END IF;

    PERFORM public.assert_card_potential_integrity(
        v_target_rarity, v_target_overall, v_target_potential, NULL
    );

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
$function$;

CREATE OR REPLACE FUNCTION public.transfer_mentor_xp(p_owner_id bigint, p_source_card_id uuid, p_target_card_id uuid, p_mentor_units integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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

    PERFORM public.assert_card_potential_integrity(
        v_src.rarity, v_src.overall, v_src.potential, v_src.base_potential
    );
    PERFORM public.assert_card_potential_integrity(
        v_tgt.rarity, v_tgt.overall, v_tgt.potential, v_tgt.base_potential
    );

    IF COALESCE(v_src.overall, 0) < public.effective_card_potential(v_src.rarity, v_src.potential) THEN
        RAISE EXCEPTION 'Source card has not reached potential ceiling';
    END IF;

    IF COALESCE(v_src.skill_points, 0) < v_sp_spent THEN
        RAISE EXCEPTION 'Insufficient skill points';
    END IF;

    IF COALESCE(v_tgt.overall, 0) >= public.effective_card_potential(v_tgt.rarity, v_tgt.potential) THEN
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
$function$;


ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_potential_rarity_cap_chk;
ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_potential_rarity_cap_chk
    CHECK (
        public.rarity_potential_cap(rarity) IS NOT NULL
        AND potential <= public.rarity_potential_cap(rarity)
    ) NOT VALID;

ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_base_potential_rarity_cap_chk;
ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_base_potential_rarity_cap_chk
    CHECK (
        public.rarity_potential_cap(rarity) IS NOT NULL
        AND (base_potential IS NULL OR base_potential <= public.rarity_potential_cap(rarity))
    ) NOT VALID;

ALTER TABLE public.player_cards
    DROP CONSTRAINT IF EXISTS player_cards_overall_potential_chk;
ALTER TABLE public.player_cards
    ADD CONSTRAINT player_cards_overall_potential_chk
    CHECK (overall <= potential) NOT VALID;

DO $$
DECLARE
    missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO missing
    FROM (
        VALUES
            ('function:rarity_potential_cap'),
            ('function:effective_card_potential'),
            ('function:assert_card_potential_integrity'),
            ('table:public.potential_cap_repair_audit'),
            ('policy:public.potential_cap_repair_audit.potential_cap_repair_audit_select'),
            ('policy:public.potential_cap_repair_audit.potential_cap_repair_audit_insert'),
            ('policy:public.potential_cap_repair_audit.potential_cap_repair_audit_update')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
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
                WHEN 'rarity_potential_cap'
                    THEN to_regprocedure('public.rarity_potential_cap(text)')
                WHEN 'effective_card_potential'
                    THEN to_regprocedure('public.effective_card_potential(text,integer)')
                WHEN 'assert_card_potential_integrity'
                    THEN to_regprocedure('public.assert_card_potential_integrity(text,integer,integer,integer)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF missing IS NOT NULL THEN
        RAISE EXCEPTION '088 rarity potential guards missing: %', missing;
    END IF;
END $$;

-- 035: US-29 — process_match_result schema fix, atomic daily pack, matchday reminder dedup

ALTER TABLE public.player_cards
    ADD COLUMN IF NOT EXISTS recent_match_ratings JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Fix process_match_result: use base_potential (exists since 017), not missing initial_potential
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

        SELECT age, potential, base_potential, recent_match_ratings
        INTO v_age, v_pot, v_init_pot, v_recent
        FROM public.player_cards
        WHERE id = v_card_id
        FOR UPDATE;

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
                morale = LEAST(100, GREATEST(10, morale + v_morale_delta)),
                recent_match_ratings = v_recent,
                potential = v_pot
            WHERE id = v_card_id;
        ELSE
            UPDATE public.player_cards
            SET morale = LEAST(100, GREATEST(10, morale + v_morale_delta))
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

GRANT ALL PRIVILEGES ON FUNCTION public.process_match_result(text, uuid[], integer, numeric[], integer[])
    TO anon, authenticated, service_role;

-- Atomic daily pack claim (store hub)
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
            potential INT, base_potential INT, age INT
        )
    LOOP
        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age
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
            COALESCE(v_card.age, 25)
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

GRANT ALL PRIVILEGES ON FUNCTION public.claim_daily_pack(BIGINT, JSONB)
    TO anon, authenticated, service_role;

-- Matchday reminder dedup (US-29f)
CREATE TABLE IF NOT EXISTS public.league_matchday_reminders (
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    matchday INTEGER NOT NULL,
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    reminded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season_id, matchday, player_id)
);

ALTER TABLE public.league_matchday_reminders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS league_matchday_reminders_select ON public.league_matchday_reminders;
DROP POLICY IF EXISTS league_matchday_reminders_insert ON public.league_matchday_reminders;

CREATE POLICY league_matchday_reminders_select ON public.league_matchday_reminders
    FOR SELECT TO anon, authenticated, service_role USING (true);

CREATE POLICY league_matchday_reminders_insert ON public.league_matchday_reminders
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

GRANT SELECT, INSERT ON public.league_matchday_reminders TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('column:public.player_cards.recent_match_ratings'),
            ('column:public.league_seasons.announcement_message_id'),
            ('function:process_match_result'),
            ('function:claim_daily_pack'),
            ('table:public.league_matchday_reminders'),
            ('policy:public.league_matchday_reminders.league_matchday_reminders_select'),
            ('policy:public.league_matchday_reminders.league_matchday_reminders_insert')
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
        OR (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
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
                WHEN 'process_match_result' THEN
                    to_regprocedure('public.process_match_result(text,uuid[],integer,numeric[],integer[])')
                WHEN 'claim_daily_pack' THEN
                    to_regprocedure('public.claim_daily_pack(bigint,jsonb)')
                ELSE NULL
            END IS NOT NULL
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

-- 067_support_legendary_reward.sql
-- One-shot Legendary thank-you for early supporters (Recover update).

INSERT INTO public.game_config (key, value_json) VALUES
    ('support_legendary_reward_enabled', 'true')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.support_legendary_reward_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('support_legendary_reward_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

CREATE TABLE IF NOT EXISTS public.support_legendary_rewards (
    discord_id BIGINT PRIMARY KEY,
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    claimed BOOLEAN NOT NULL DEFAULT FALSE,
    claimed_at TIMESTAMPTZ,
    card_id UUID REFERENCES public.player_cards(id),
    pending_card JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS support_legendary_rewards_unclaimed_idx
    ON public.support_legendary_rewards (claimed, notified)
    WHERE claimed = FALSE;

ALTER TABLE public.support_legendary_rewards ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS support_legendary_rewards_select ON public.support_legendary_rewards;
DROP POLICY IF EXISTS support_legendary_rewards_insert ON public.support_legendary_rewards;
DROP POLICY IF EXISTS support_legendary_rewards_update ON public.support_legendary_rewards;

CREATE POLICY support_legendary_rewards_select ON public.support_legendary_rewards
    FOR SELECT TO anon, authenticated, service_role
    USING (true);

CREATE POLICY support_legendary_rewards_insert ON public.support_legendary_rewards
    FOR INSERT TO anon, authenticated, service_role
    WITH CHECK (true);

CREATE POLICY support_legendary_rewards_update ON public.support_legendary_rewards
    FOR UPDATE TO anon, authenticated, service_role
    USING (true)
    WITH CHECK (true);

-- Eligible Discord IDs (thank-you for Recover update supporters)
INSERT INTO public.support_legendary_rewards (discord_id) VALUES
    (830343973976408074),
    (917714032822198333),
    (840864839240253440),
    (892305363657961513),
    (806810293388181514),
    (816259135523520512),
    (560340920524865539)
ON CONFLICT (discord_id) DO NOTHING;

CREATE OR REPLACE FUNCTION public.prepare_support_legendary_reward(
    p_owner_id BIGINT,
    p_card JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_row public.support_legendary_rewards%ROWTYPE;
BEGIN
    IF NOT public.support_legendary_reward_enabled() THEN
        RAISE EXCEPTION 'Support legendary reward is disabled';
    END IF;

    IF p_card IS NULL OR jsonb_typeof(p_card) <> 'object' THEN
        RAISE EXCEPTION 'Invalid reward card payload';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.players WHERE discord_id = p_owner_id) THEN
        RAISE EXCEPTION 'Club not found — register before claiming';
    END IF;

    SELECT * INTO v_row
    FROM public.support_legendary_rewards
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Not eligible for this reward';
    END IF;

    IF v_row.claimed THEN
        RAISE EXCEPTION 'Legendary reward already claimed';
    END IF;

    IF v_row.pending_card IS NOT NULL THEN
        RETURN jsonb_build_object(
            'pending_card', v_row.pending_card,
            'already_prepared', TRUE
        );
    END IF;

    UPDATE public.support_legendary_rewards
    SET pending_card = p_card
    WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object(
        'pending_card', p_card,
        'already_prepared', FALSE
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.claim_support_legendary_reward(
    p_owner_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_row public.support_legendary_rewards%ROWTYPE;
    v_card JSONB;
    v_dob DATE;
    v_card_id UUID;
BEGIN
    IF NOT public.support_legendary_reward_enabled() THEN
        RAISE EXCEPTION 'Support legendary reward is disabled';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.players WHERE discord_id = p_owner_id) THEN
        RAISE EXCEPTION 'Club not found — register before claiming';
    END IF;

    SELECT * INTO v_row
    FROM public.support_legendary_rewards
    WHERE discord_id = p_owner_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Not eligible for this reward';
    END IF;

    IF v_row.claimed THEN
        RAISE EXCEPTION 'Legendary reward already claimed';
    END IF;

    IF v_row.pending_card IS NULL THEN
        RAISE EXCEPTION 'Reward not prepared yet — open /development and try again';
    END IF;

    v_card := v_row.pending_card;
    v_dob := NULLIF(v_card->>'date_of_birth', '')::DATE;

    INSERT INTO public.player_cards (
        owner_id, name, position, rarity, base_rating, level, overall,
        pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
    ) VALUES (
        p_owner_id,
        v_card->>'name',
        v_card->>'position',
        COALESCE(v_card->>'rarity', 'Legendary'),
        COALESCE((v_card->>'base_rating')::INTEGER, (v_card->>'overall')::INTEGER),
        1,
        (v_card->>'overall')::INTEGER,
        COALESCE((v_card->>'pac')::INTEGER, 50),
        COALESCE((v_card->>'sho')::INTEGER, 50),
        COALESCE((v_card->>'pas')::INTEGER, 50),
        COALESCE((v_card->>'dri')::INTEGER, 50),
        COALESCE((v_card->>'def')::INTEGER, 50),
        COALESCE((v_card->>'phy')::INTEGER, 50),
        COALESCE((v_card->>'potential')::INTEGER, (v_card->>'overall')::INTEGER),
        COALESCE((v_card->>'base_potential')::INTEGER, (v_card->>'potential')::INTEGER, (v_card->>'overall')::INTEGER),
        CASE
            WHEN v_dob IS NOT NULL THEN public.card_age_from_dob(v_dob)
            ELSE COALESCE((v_card->>'age')::INTEGER, 20)
        END,
        v_dob,
        COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced')
    )
    RETURNING id INTO v_card_id;

    UPDATE public.support_legendary_rewards
    SET claimed = TRUE,
        claimed_at = NOW(),
        card_id = v_card_id,
        notified = TRUE
    WHERE discord_id = p_owner_id;

    RETURN jsonb_build_object(
        'card_id', v_card_id,
        'name', v_card->>'name',
        'position', v_card->>'position',
        'overall', (v_card->>'overall')::INTEGER,
        'potential', COALESCE((v_card->>'potential')::INTEGER, (v_card->>'overall')::INTEGER),
        'rarity', COALESCE(v_card->>'rarity', 'Legendary'),
        'role', COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced')
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.support_legendary_reward_pending(p_owner_id BIGINT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT public.support_legendary_reward_enabled()
       AND EXISTS (
           SELECT 1
           FROM public.support_legendary_rewards r
           WHERE r.discord_id = p_owner_id
             AND r.claimed = FALSE
       );
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.support_legendary_reward_enabled()
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.prepare_support_legendary_reward(BIGINT, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_support_legendary_reward(BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.support_legendary_reward_pending(BIGINT)
    TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.support_legendary_rewards
    TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT;
BEGIN
    SELECT string_agg(req.obj, ', ')
    INTO v_missing
    FROM (
        VALUES
            ('table:public.support_legendary_rewards'),
            ('function:prepare_support_legendary_reward'),
            ('function:claim_support_legendary_reward'),
            ('function:support_legendary_reward_pending'),
            ('policy:public.support_legendary_rewards.support_legendary_rewards_select'),
            ('policy:public.support_legendary_rewards.support_legendary_rewards_update')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (req.obj = 'function:prepare_support_legendary_reward'
            AND to_regprocedure('public.prepare_support_legendary_reward(bigint,jsonb)') IS NOT NULL)
        OR (req.obj = 'function:claim_support_legendary_reward'
            AND to_regprocedure('public.claim_support_legendary_reward(bigint)') IS NOT NULL)
        OR (req.obj = 'function:support_legendary_reward_pending'
            AND to_regprocedure('public.support_legendary_reward_pending(bigint)') IS NOT NULL)
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = 'public'
                  AND pol.tablename = 'support_legendary_rewards'
                  AND pol.policyname = split_part(req.obj, '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 067 guard failed — missing: %', v_missing;
    END IF;
END;
$$;

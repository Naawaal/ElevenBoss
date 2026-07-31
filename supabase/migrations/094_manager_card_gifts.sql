-- 094: One-time manager card gifts (AC-39n)
-- Snapshot existing non-AI managers for Epic gifts; special Legendary MID for one club.
-- US-42.1 / 42.2 / 42.9 — ownership, free roster (not auto-XI), potential integrity.

INSERT INTO public.game_config (key, value_json) VALUES
    ('manager_card_gifts_enabled', 'true')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.manager_card_gifts_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('manager_card_gifts_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

CREATE TABLE IF NOT EXISTS public.manager_card_gifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id TEXT NOT NULL,
    discord_id BIGINT NOT NULL,
    gift_slot TEXT NOT NULL,
    dm_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (dm_status IN ('pending', 'sent', 'blocked')),
    claimed BOOLEAN NOT NULL DEFAULT FALSE,
    claimed_at TIMESTAMPTZ,
    card_id UUID REFERENCES public.player_cards(id),
    pending_card JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT manager_card_gifts_slot_chk CHECK (
        gift_slot IN ('epic', 'legendary_mid')
    ),
    CONSTRAINT manager_card_gifts_uniq UNIQUE (campaign_id, discord_id, gift_slot)
);

CREATE INDEX IF NOT EXISTS manager_card_gifts_unclaimed_idx
    ON public.manager_card_gifts (campaign_id, claimed, dm_status)
    WHERE claimed = FALSE;

CREATE INDEX IF NOT EXISTS manager_card_gifts_owner_idx
    ON public.manager_card_gifts (discord_id, claimed);

ALTER TABLE public.manager_card_gifts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS manager_card_gifts_select ON public.manager_card_gifts;
DROP POLICY IF EXISTS manager_card_gifts_insert ON public.manager_card_gifts;
DROP POLICY IF EXISTS manager_card_gifts_update ON public.manager_card_gifts;

CREATE POLICY manager_card_gifts_select ON public.manager_card_gifts
    FOR SELECT TO anon, authenticated, service_role
    USING (true);

CREATE POLICY manager_card_gifts_insert ON public.manager_card_gifts
    FOR INSERT TO anon, authenticated, service_role
    WITH CHECK (true);

CREATE POLICY manager_card_gifts_update ON public.manager_card_gifts
    FOR UPDATE TO anon, authenticated, service_role
    USING (true)
    WITH CHECK (true);

-- Snapshot: one Epic slot per existing human manager
INSERT INTO public.manager_card_gifts (campaign_id, discord_id, gift_slot)
SELECT 'manager_card_gifts_20260731', p.discord_id, 'epic'
FROM public.players p
WHERE COALESCE(p.is_ai, false) = false
ON CONFLICT (campaign_id, discord_id, gift_slot) DO NOTHING;

-- Special second gift: Legendary MID @ 92 OVR for Mirai MidNight manager
INSERT INTO public.manager_card_gifts (campaign_id, discord_id, gift_slot)
VALUES ('manager_card_gifts_20260731', 976054227459776582, 'legendary_mid')
ON CONFLICT (campaign_id, discord_id, gift_slot) DO NOTHING;

CREATE OR REPLACE FUNCTION public.prepare_manager_card_gifts(
    p_owner_id BIGINT,
    p_gifts JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_item JSONB;
    v_slot TEXT;
    v_card JSONB;
    v_row public.manager_card_gifts%ROWTYPE;
    v_prepared JSONB := '[]'::jsonb;
    v_campaign CONSTANT TEXT := 'manager_card_gifts_20260731';
BEGIN
    IF NOT public.manager_card_gifts_enabled() THEN
        RAISE EXCEPTION 'Manager card gifts are disabled';
    END IF;

    IF p_gifts IS NULL OR jsonb_typeof(p_gifts) <> 'array' THEN
        RAISE EXCEPTION 'Invalid gift payload';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.players WHERE discord_id = p_owner_id) THEN
        RAISE EXCEPTION 'Club not found — register before claiming';
    END IF;

    FOR v_item IN SELECT value FROM jsonb_array_elements(p_gifts)
    LOOP
        v_slot := NULLIF(trim(v_item->>'gift_slot'), '');
        v_card := v_item->'card';
        IF v_slot IS NULL OR v_card IS NULL OR jsonb_typeof(v_card) <> 'object' THEN
            RAISE EXCEPTION 'Invalid gift payload';
        END IF;

        SELECT * INTO v_row
        FROM public.manager_card_gifts
        WHERE campaign_id = v_campaign
          AND discord_id = p_owner_id
          AND gift_slot = v_slot
        FOR UPDATE;

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        IF v_row.claimed THEN
            CONTINUE;
        END IF;

        IF v_row.pending_card IS NULL THEN
            UPDATE public.manager_card_gifts
            SET pending_card = v_card
            WHERE id = v_row.id;
            v_prepared := v_prepared || jsonb_build_array(
                jsonb_build_object(
                    'gift_slot', v_slot,
                    'card', v_card,
                    'already_prepared', FALSE
                )
            );
        ELSE
            v_prepared := v_prepared || jsonb_build_array(
                jsonb_build_object(
                    'gift_slot', v_slot,
                    'card', v_row.pending_card,
                    'already_prepared', TRUE
                )
            );
        END IF;
    END LOOP;

    RETURN jsonb_build_object('gifts', v_prepared);
END;
$$;

CREATE OR REPLACE FUNCTION public.claim_manager_card_gifts(
    p_owner_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_row public.manager_card_gifts%ROWTYPE;
    v_card JSONB;
    v_dob DATE;
    v_card_id UUID;
    v_pot INT;
    v_base_pot INT;
    v_claimed JSONB := '[]'::jsonb;
    v_any_unclaimed BOOLEAN := FALSE;
    v_campaign CONSTANT TEXT := 'manager_card_gifts_20260731';
BEGIN
    IF NOT public.manager_card_gifts_enabled() THEN
        RAISE EXCEPTION 'Manager card gifts are disabled';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.players WHERE discord_id = p_owner_id FOR UPDATE
    ) THEN
        RAISE EXCEPTION 'Club not found — register before claiming';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.manager_card_gifts
        WHERE campaign_id = v_campaign
          AND discord_id = p_owner_id
    ) THEN
        RAISE EXCEPTION 'Not eligible for this reward';
    END IF;

    FOR v_row IN
        SELECT *
        FROM public.manager_card_gifts
        WHERE campaign_id = v_campaign
          AND discord_id = p_owner_id
        ORDER BY gift_slot
        FOR UPDATE
    LOOP
        IF v_row.claimed THEN
            IF v_row.card_id IS NOT NULL AND v_row.pending_card IS NOT NULL THEN
                v_card := v_row.pending_card;
                v_claimed := v_claimed || jsonb_build_array(
                    jsonb_build_object(
                        'gift_slot', v_row.gift_slot,
                        'card_id', v_row.card_id,
                        'name', v_card->>'name',
                        'position', v_card->>'position',
                        'overall', (v_card->>'overall')::INTEGER,
                        'potential', COALESCE((v_card->>'potential')::INTEGER, (v_card->>'overall')::INTEGER),
                        'rarity', COALESCE(v_card->>'rarity', 'Epic'),
                        'role', COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced'),
                        'already_claimed', TRUE
                    )
                );
            END IF;
            CONTINUE;
        END IF;

        v_any_unclaimed := TRUE;

        IF v_row.pending_card IS NULL THEN
            RAISE EXCEPTION 'Reward not prepared yet — open /development and try again';
        END IF;

        v_card := v_row.pending_card;
        v_pot := COALESCE((v_card->>'potential')::INT, (v_card->>'overall')::INT);
        v_base_pot := COALESCE((v_card->>'base_potential')::INT, v_pot);

        PERFORM public.assert_card_potential_integrity(
            COALESCE(v_card->>'rarity', 'Epic'),
            COALESCE((v_card->>'overall')::INT, 0),
            v_pot,
            v_base_pot
        );

        v_dob := NULLIF(v_card->>'date_of_birth', '')::DATE;

        INSERT INTO public.player_cards (
            owner_id, name, position, rarity, base_rating, level, overall,
            pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role
        ) VALUES (
            p_owner_id,
            v_card->>'name',
            v_card->>'position',
            COALESCE(v_card->>'rarity', 'Epic'),
            COALESCE((v_card->>'base_rating')::INTEGER, (v_card->>'overall')::INTEGER),
            1,
            (v_card->>'overall')::INTEGER,
            COALESCE((v_card->>'pac')::INTEGER, 50),
            COALESCE((v_card->>'sho')::INTEGER, 50),
            COALESCE((v_card->>'pas')::INTEGER, 50),
            COALESCE((v_card->>'dri')::INTEGER, 50),
            COALESCE((v_card->>'def')::INTEGER, 50),
            COALESCE((v_card->>'phy')::INTEGER, 50),
            v_pot,
            v_base_pot,
            CASE
                WHEN v_dob IS NOT NULL THEN public.card_age_from_dob(v_dob)
                ELSE COALESCE((v_card->>'age')::INTEGER, 20)
            END,
            v_dob,
            COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced')
        )
        RETURNING id INTO v_card_id;

        PERFORM public.ensure_card_ownership_open(
            v_card_id, p_owner_id, 'manager_card_gift'
        );

        UPDATE public.manager_card_gifts
        SET claimed = TRUE,
            claimed_at = NOW(),
            card_id = v_card_id,
            dm_status = CASE
                WHEN dm_status = 'pending' THEN 'sent'
                ELSE dm_status
            END
        WHERE id = v_row.id;

        v_claimed := v_claimed || jsonb_build_array(
            jsonb_build_object(
                'gift_slot', v_row.gift_slot,
                'card_id', v_card_id,
                'name', v_card->>'name',
                'position', v_card->>'position',
                'overall', (v_card->>'overall')::INTEGER,
                'potential', v_pot,
                'rarity', COALESCE(v_card->>'rarity', 'Epic'),
                'role', COALESCE(NULLIF(trim(v_card->>'role'), ''), 'Balanced'),
                'already_claimed', FALSE
            )
        );
    END LOOP;

    IF jsonb_array_length(v_claimed) = 0 THEN
        RAISE EXCEPTION 'Not eligible for this reward';
    END IF;

    IF NOT v_any_unclaimed THEN
        RETURN jsonb_build_object(
            'status', 'already_claimed',
            'cards', v_claimed
        );
    END IF;

    RETURN jsonb_build_object(
        'status', 'claimed',
        'cards', v_claimed
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.manager_card_gifts_pending(p_owner_id BIGINT)
RETURNS INTEGER
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT CASE
        WHEN NOT public.manager_card_gifts_enabled() THEN 0
        ELSE (
            SELECT COUNT(*)::INTEGER
            FROM public.manager_card_gifts r
            WHERE r.campaign_id = 'manager_card_gifts_20260731'
              AND r.discord_id = p_owner_id
              AND r.claimed = FALSE
        )
    END;
$$;

CREATE OR REPLACE FUNCTION public.set_manager_card_gift_dm_status(
    p_owner_id BIGINT,
    p_status TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_status TEXT := lower(trim(p_status));
    v_updated INTEGER := 0;
    v_campaign CONSTANT TEXT := 'manager_card_gifts_20260731';
BEGIN
    IF v_status NOT IN ('sent', 'blocked') THEN
        RAISE EXCEPTION 'Invalid gift DM status';
    END IF;

    UPDATE public.manager_card_gifts
    SET dm_status = v_status
    WHERE campaign_id = v_campaign
      AND discord_id = p_owner_id
      AND claimed = FALSE
      AND dm_status = 'pending';

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN jsonb_build_object('updated', v_updated, 'status', v_status);
END;
$$;

-- Forward-replace hub state (do not edit applied 093)
CREATE OR REPLACE FUNCTION public.get_development_hub_state(p_owner_id bigint)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_pending int := 0;
    v_leg_pending boolean := false;
    v_leg_card jsonb := NULL;
    v_leg_enabled boolean := false;
    v_gift_pending int := 0;
    v_gift_cards jsonb := '[]'::jsonb;
BEGIN
    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'player_not_found');
    END IF;

    v_pending := public.count_unclaimed_level_rewards(p_owner_id);

    BEGIN
        v_leg_enabled := public.support_legendary_reward_enabled();
    EXCEPTION WHEN OTHERS THEN
        v_leg_enabled := false;
    END;

    IF v_leg_enabled THEN
        v_leg_pending := public.support_legendary_reward_pending(p_owner_id);
        IF v_leg_pending THEN
            SELECT r.pending_card INTO v_leg_card
            FROM public.support_legendary_rewards r
            WHERE r.discord_id = p_owner_id
              AND r.claimed = FALSE
            LIMIT 1;
        END IF;
    END IF;

    BEGIN
        v_gift_pending := public.manager_card_gifts_pending(p_owner_id);
    EXCEPTION WHEN OTHERS THEN
        v_gift_pending := 0;
    END;

    IF v_gift_pending > 0 THEN
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'gift_slot', g.gift_slot,
                    'pending_card', g.pending_card
                )
                ORDER BY g.gift_slot
            ),
            '[]'::jsonb
        )
        INTO v_gift_cards
        FROM public.manager_card_gifts g
        WHERE g.campaign_id = 'manager_card_gifts_20260731'
          AND g.discord_id = p_owner_id
          AND g.claimed = FALSE;
    END IF;

    RETURN jsonb_build_object(
        'ok', true,
        'club_name', v_player.club_name,
        'action_energy', COALESCE(v_player.action_energy, 0),
        'max_energy', COALESCE(v_player.max_energy, 120),
        'pending_reward_count', v_pending,
        'legendary_pending', v_leg_pending,
        'legendary_pending_card', v_leg_card,
        'manager_gift_pending', v_gift_pending,
        'manager_gift_cards', v_gift_cards
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.manager_card_gifts_enabled()
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.prepare_manager_card_gifts(BIGINT, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.claim_manager_card_gifts(BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.manager_card_gifts_pending(BIGINT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.set_manager_card_gift_dm_status(BIGINT, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.get_development_hub_state(BIGINT)
    TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON public.manager_card_gifts
    TO anon, authenticated, service_role;

DO $$
DECLARE
    v_missing TEXT;
BEGIN
    SELECT string_agg(req.obj, ', ')
    INTO v_missing
    FROM (
        VALUES
            ('table:public.manager_card_gifts'),
            ('function:prepare_manager_card_gifts'),
            ('function:claim_manager_card_gifts'),
            ('function:manager_card_gifts_pending'),
            ('function:set_manager_card_gift_dm_status'),
            ('function:get_development_hub_state'),
            ('policy:public.manager_card_gifts.manager_card_gifts_select'),
            ('policy:public.manager_card_gifts.manager_card_gifts_update')
    ) AS req(obj)
    WHERE NOT (
        (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (req.obj = 'function:prepare_manager_card_gifts'
            AND to_regprocedure('public.prepare_manager_card_gifts(bigint,jsonb)') IS NOT NULL)
        OR (req.obj = 'function:claim_manager_card_gifts'
            AND to_regprocedure('public.claim_manager_card_gifts(bigint)') IS NOT NULL)
        OR (req.obj = 'function:manager_card_gifts_pending'
            AND to_regprocedure('public.manager_card_gifts_pending(bigint)') IS NOT NULL)
        OR (req.obj = 'function:set_manager_card_gift_dm_status'
            AND to_regprocedure('public.set_manager_card_gift_dm_status(bigint,text)') IS NOT NULL)
        OR (req.obj = 'function:get_development_hub_state'
            AND to_regprocedure('public.get_development_hub_state(bigint)') IS NOT NULL)
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1 FROM pg_policies pol
                WHERE pol.schemaname = 'public'
                  AND pol.tablename = 'manager_card_gifts'
                  AND pol.policyname = split_part(req.obj, '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 094 guard failed — missing: %', v_missing;
    END IF;
END;
$$;

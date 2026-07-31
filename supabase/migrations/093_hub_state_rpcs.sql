-- 093: Development hub / skills / mentor read-state RPCs (050 US5)
-- Read-only: no ensure/prepare legendary, no claims, no energy sync writes.

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

    RETURN jsonb_build_object(
        'ok', true,
        'club_name', v_player.club_name,
        'action_energy', COALESCE(v_player.action_energy, 0),
        'max_energy', COALESCE(v_player.max_energy, 120),
        'pending_reward_count', v_pending,
        'legendary_pending', v_leg_pending,
        'legendary_pending_card', v_leg_card
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_skill_allocation_hub(
    p_owner_id bigint,
    p_card_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_roster jsonb;
    v_card jsonb;
    v_pick uuid;
BEGIN
    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'id', c.id,
                'name', c.name,
                'overall', c.overall,
                'in_academy', COALESCE(c.in_academy, false)
            )
            ORDER BY c.overall DESC
        ),
        '[]'::jsonb
    )
    INTO v_roster
    FROM public.player_cards c
    WHERE c.owner_id = p_owner_id
      AND COALESCE(c.in_academy, false) = false;

    IF jsonb_array_length(v_roster) = 0 THEN
        RETURN jsonb_build_object(
            'ok', true,
            'roster', '[]'::jsonb,
            'card', NULL
        );
    END IF;

    v_pick := p_card_id;
    IF v_pick IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.player_cards c
           WHERE c.id = v_pick
             AND c.owner_id = p_owner_id
             AND COALESCE(c.in_academy, false) = false
       )
    THEN
        v_pick := (v_roster->0->>'id')::uuid;
    END IF;

    SELECT to_jsonb(c.*) INTO v_card
    FROM public.player_cards c
    WHERE c.id = v_pick AND c.owner_id = p_owner_id;

    RETURN jsonb_build_object(
        'ok', true,
        'roster', v_roster,
        'card', v_card
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_mentor_targets(
    p_owner_id bigint,
    p_source_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_rows jsonb;
    v_l_max constant int := 100;
BEGIN
    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'id', c.id,
                'name', c.name,
                'overall', c.overall,
                'potential', c.potential,
                'level', COALESCE(c.level, 1),
                'xp', COALESCE(c.xp, 0),
                'skill_points', COALESCE(c.skill_points, 0),
                'in_academy', COALESCE(c.in_academy, false)
            )
            ORDER BY COALESCE(c.level, 1)
        ),
        '[]'::jsonb
    )
    INTO v_rows
    FROM public.player_cards c
    WHERE c.owner_id = p_owner_id
      AND c.id <> p_source_id
      AND COALESCE(c.in_academy, false) = false
      AND c.overall < c.potential
      AND COALESCE(c.level, 1) < v_l_max
      AND NOT EXISTS (
          SELECT 1
          FROM public.transfer_listings tl
          WHERE tl.card_id = c.id
            AND tl.status = 'active'
      );

    RETURN jsonb_build_object('ok', true, 'targets', v_rows);
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_development_hub_state(bigint)
    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_skill_allocation_hub(bigint, uuid)
    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_mentor_targets(bigint, uuid)
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.get_development_hub_state(bigint)') IS NULL THEN
        RAISE EXCEPTION '093 guard failed: get_development_hub_state';
    END IF;
    IF to_regprocedure('public.get_skill_allocation_hub(bigint, uuid)') IS NULL THEN
        RAISE EXCEPTION '093 guard failed: get_skill_allocation_hub';
    END IF;
    IF to_regprocedure('public.get_mentor_targets(bigint, uuid)') IS NULL THEN
        RAISE EXCEPTION '093 guard failed: get_mentor_targets';
    END IF;
END $$;

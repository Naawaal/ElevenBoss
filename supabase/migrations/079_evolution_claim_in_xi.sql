-- 079: Allow evolution claim/cancel when card is Evolving + InXI (normal for starters).
-- Fixes CARD_STATE: state_conflict blocking claim_evolution_reward for XI players.

CREATE OR REPLACE FUNCTION public.assert_card_action_allowed(
    p_owner_id BIGINT,
    p_card_id UUID,
    p_action TEXT
) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
    v_retired BOOLEAN;
    v_hospital BOOLEAN;
    v_academy BOOLEAN;
    v_injury INTEGER;
    v_listed BOOLEAN;
    v_evolving BOOLEAN;
    v_training BOOLEAN;
    v_in_xi BOOLEAN;
    v_busy INT := 0;
    v_primary TEXT;
    v_mutation BOOLEAN;
BEGIN
    IF p_action IS NULL OR btrim(p_action) = '' THEN
        RAISE EXCEPTION 'CARD_STATE: missing action';
    END IF;

    SELECT owner_id,
           COALESCE(is_retired, FALSE),
           COALESCE(in_hospital, FALSE),
           COALESCE(in_academy, FALSE),
           injury_tier
    INTO v_owner, v_retired, v_hospital, v_academy, v_injury
    FROM public.player_cards
    WHERE id = p_card_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    IF v_owner IS DISTINCT FROM p_owner_id THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    v_listed := EXISTS (
        SELECT 1 FROM public.transfer_listings
        WHERE card_id = p_card_id AND status = 'active'
    );
    v_evolving := EXISTS (
        SELECT 1 FROM public.active_evolutions
        WHERE card_id = p_card_id AND status = 'active'
    );
    v_training := EXISTS (
        SELECT 1 FROM public.active_training
        WHERE card_id = p_card_id AND end_time > NOW()
    );
    v_in_xi := EXISTS (
        SELECT 1 FROM public.squad_assignments
        WHERE player_card_id = p_card_id
    );

    IF v_retired THEN v_busy := v_busy + 1; END IF;
    IF v_listed THEN v_busy := v_busy + 1; END IF;
    IF v_hospital THEN v_busy := v_busy + 1; END IF;
    IF v_evolving THEN v_busy := v_busy + 1; END IF;
    IF v_training THEN v_busy := v_busy + 1; END IF;
    IF v_academy THEN v_busy := v_busy + 1; END IF;

    IF v_busy > 1 THEN
        RAISE EXCEPTION 'CARD_STATE: state_conflict';
    END IF;
    IF v_in_xi AND v_busy >= 1 THEN
        -- Starters completing evolution tracks stay in XI; claim/cancel must work (031 US3).
        IF NOT (
            v_evolving
            AND NOT v_retired
            AND NOT v_listed
            AND NOT v_hospital
            AND NOT v_training
            AND NOT v_academy
        ) THEN
            RAISE EXCEPTION 'CARD_STATE: state_conflict';
        END IF;
    END IF;

    -- Priority mirrors packages/player_engine/card_state.py
    IF v_retired THEN
        v_primary := 'Retired';
    ELSIF v_listed THEN
        v_primary := 'Listed';
    ELSIF v_hospital THEN
        v_primary := 'Hospitalized';
    ELSIF v_evolving THEN
        v_primary := 'Evolving';
    ELSIF v_training THEN
        v_primary := 'TrainingBusy';
    ELSIF v_academy THEN
        v_primary := 'InAcademy';
    ELSIF v_in_xi THEN
        v_primary := 'InXI';
    ELSE
        v_primary := 'RosterFree';
    END IF;

    v_mutation := p_action IS DISTINCT FROM 'view_profile';
    IF v_mutation THEN
        PERFORM public.assert_not_in_match(p_owner_id);
    END IF;

    -- Matrix Allow sets (spec §B.5)
    IF p_action = 'view_profile' THEN
        RETURN;
    ELSIF p_action = 'assign_xi' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks assign_xi', v_primary;
        END IF;
    ELSIF p_action = 'bench' THEN
        IF v_primary IS DISTINCT FROM 'InXI' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks bench', v_primary;
        END IF;
    ELSIF p_action = 'match_include' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks match_include', v_primary;
        END IF;
    ELSIF p_action = 'drill' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks drill', v_primary;
        END IF;
    ELSIF p_action = 'fusion' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks fusion', v_primary;
        END IF;
    ELSIF p_action = 'allocate' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks allocate', v_primary;
        END IF;
    ELSIF p_action = 'recover_fatigue' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks recover_fatigue', v_primary;
        END IF;
    ELSIF p_action = 'start_evolution' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks start_evolution', v_primary;
        END IF;
    ELSIF p_action IN ('claim_evolution', 'cancel_evolution') THEN
        IF v_primary IS DISTINCT FROM 'Evolving' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    ELSIF p_action = 'admit_hospital' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks admit_hospital', v_primary;
        END IF;
    ELSIF p_action = 'discharge_hospital' THEN
        IF v_primary IS DISTINCT FROM 'Hospitalized' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks discharge_hospital', v_primary;
        END IF;
    ELSIF p_action = 'list_transfer' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks list_transfer', v_primary;
        END IF;
        -- InjuryPlayOn modifier (fatigue alone does NOT block list)
        IF v_injury IS NOT NULL OR v_hospital THEN
            RAISE EXCEPTION 'CARD_STATE: injury blocks list_transfer';
        END IF;
    ELSIF p_action = 'cancel_listing' THEN
        IF v_primary IS DISTINCT FROM 'Listed' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks cancel_listing', v_primary;
        END IF;
    ELSIF p_action = 'agent_sell' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks agent_sell', v_primary;
        END IF;
        IF v_injury IS NOT NULL OR v_hospital THEN
            RAISE EXCEPTION 'CARD_STATE: injury blocks agent_sell';
        END IF;
    ELSIF p_action = 'academy_seat' THEN
        IF v_primary IS DISTINCT FROM 'RosterFree' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks academy_seat', v_primary;
        END IF;
    ELSIF p_action IN ('academy_promote', 'academy_release') THEN
        IF v_primary IS DISTINCT FROM 'InAcademy' THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    ELSIF p_action = 'retire' THEN
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks retire', v_primary;
        END IF;
    ELSE
        -- Default: only RosterFree / InXI for unknown future mutations
        IF v_primary NOT IN ('RosterFree', 'InXI') THEN
            RAISE EXCEPTION 'CARD_STATE: % blocks %', v_primary, p_action;
        END IF;
    END IF;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.assert_card_action_allowed(BIGINT, UUID, TEXT)
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.assert_card_action_allowed(bigint,uuid,text)') IS NULL THEN
        RAISE EXCEPTION '079 guard: assert_card_action_allowed missing';
    END IF;
END $$;

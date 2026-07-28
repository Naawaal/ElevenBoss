-- 087: Fix renew_contract permanent idempotency key (047-fix-contract-renew / US-42)
-- Old key contract_renewal:{card_id} blocked all future renews after the first success.
-- Per-attempt key: client UUID or UTC-minute bucket.

DROP FUNCTION IF EXISTS public.renew_contract(BIGINT, UUID, BIGINT, INTEGER);

CREATE OR REPLACE FUNCTION public.renew_contract(
    p_club_id BIGINT,
    p_card_id UUID,
    p_cost BIGINT,
    p_extension_days INTEGER,
    p_idempotency_key TEXT DEFAULT NULL
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_expiry TIMESTAMPTZ;
    v_age INTEGER;
    v_warn INTEGER;
    v_dob DATE;
    v_econ JSONB;
    v_key TEXT;
BEGIN
    v_warn := public.get_game_config_int('retirement_warning_age', 35)::INTEGER;

    IF NOT EXISTS (
        SELECT 1 FROM public.player_cards
        WHERE id = p_card_id AND owner_id = p_club_id AND COALESCE(is_retired, FALSE) = FALSE
    ) THEN
        RAISE EXCEPTION 'Player card not found or not owned';
    END IF;

    SELECT date_of_birth INTO v_dob FROM public.player_cards WHERE id = p_card_id;
    v_age := public.card_age_from_dob(v_dob);
    IF v_age >= v_warn THEN
        RAISE EXCEPTION 'Cannot renew contract for players age % and over', v_warn;
    END IF;

    v_key := NULLIF(btrim(COALESCE(p_idempotency_key, '')), '');
    IF v_key IS NULL THEN
        v_key := 'contract_renewal:' || p_card_id::TEXT || ':' ||
            to_char(date_trunc('minute', timezone('utc', now())), 'YYYYMMDDHH24MI');
    END IF;

    v_econ := public.apply_club_economy(
        p_club_id,
        -p_cost,
        0,
        'contract_renewal',
        v_key,
        jsonb_build_object(
            'card_id', p_card_id,
            'extension_days', p_extension_days
        )
    );

    IF COALESCE((v_econ->>'replay')::BOOLEAN, FALSE) THEN
        RETURN TRUE;
    END IF;

    SELECT contract_expires_at INTO v_expiry FROM public.player_cards WHERE id = p_card_id;
    IF v_expiry IS NULL OR v_expiry < NOW() THEN
        v_expiry := NOW();
    END IF;

    UPDATE public.player_cards
    SET contract_expires_at = v_expiry + (p_extension_days * INTERVAL '1 day')
    WHERE id = p_card_id;

    RETURN TRUE;
END;
$$;

GRANT EXECUTE ON FUNCTION public.renew_contract(BIGINT, UUID, BIGINT, INTEGER, TEXT)
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.renew_contract(bigint,uuid,bigint,integer,text)') IS NULL THEN
        RAISE EXCEPTION '087 guard failed: renew_contract(bigint,uuid,bigint,integer,text) missing';
    END IF;
    IF to_regprocedure('public.renew_contract(bigint,uuid,bigint,integer)') IS NOT NULL THEN
        RAISE EXCEPTION '087 guard failed: old 4-arg renew_contract overload still present';
    END IF;
END $$;

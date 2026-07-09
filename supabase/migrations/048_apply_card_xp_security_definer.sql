-- 048: apply_card_xp must be SECURITY DEFINER after 047 revoked anon INSERT on player_xp_log.
-- apply_club_economy got SECURITY DEFINER in 047; apply_card_xp was missed.

ALTER FUNCTION public.apply_card_xp(UUID, INTEGER, TEXT) SECURITY DEFINER;
ALTER FUNCTION public.apply_card_xp(UUID, INTEGER, TEXT) SET search_path = public;

DO $$
BEGIN
    IF NOT (
        SELECT p.prosecdef
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname = 'apply_card_xp'
          AND pg_get_function_identity_arguments(p.oid) = 'p_card_id uuid, p_xp_amount integer, p_source text'
    ) THEN
        RAISE EXCEPTION '048_apply_card_xp_security_definer guard failed';
    END IF;
END;
$$;

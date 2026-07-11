-- 049: Guard that apply_card_xp remains SECURITY DEFINER (048 must stay applied).
-- Idempotent — safe if 048 already ran. Does not alter function body.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname = 'apply_card_xp'
          AND pg_get_function_identity_arguments(p.oid) = 'p_card_id uuid, p_xp_amount integer, p_source text'
          AND p.prosecdef
    ) THEN
        RAISE EXCEPTION
            '049_verify_apply_card_xp_security_definer: apply_card_xp must be SECURITY DEFINER (apply migration 048)';
    END IF;
END;
$$;

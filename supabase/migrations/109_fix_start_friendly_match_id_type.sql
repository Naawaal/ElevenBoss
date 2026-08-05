-- Migration 109: Fix start_friendly_match p_challenge_id type to TEXT for Discord Snowflake IDs
DROP FUNCTION IF EXISTS public.start_friendly_match(UUID, BIGINT, BIGINT, JSONB);
DROP FUNCTION IF EXISTS public.start_friendly_match(TEXT, BIGINT, BIGINT, JSONB);

CREATE OR REPLACE FUNCTION public.start_friendly_match(
    p_challenge_id TEXT,
    p_home_id BIGINT,
    p_away_id BIGINT,
    p_squad_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_first_id BIGINT;
    v_second_id BIGINT;
    v_first_locked BOOLEAN;
    v_second_locked BOOLEAN;
    v_run_id UUID;
BEGIN
    -- Canonical sort to prevent deadlock
    v_first_id := LEAST(p_home_id, p_away_id);
    v_second_id := GREATEST(p_home_id, p_away_id);

    -- Check locks for both managers
    SELECT EXISTS (SELECT 1 FROM public.match_locks WHERE discord_id = v_first_id FOR UPDATE) INTO v_first_locked;
    SELECT EXISTS (SELECT 1 FROM public.match_locks WHERE discord_id = v_second_id FOR UPDATE) INTO v_second_locked;

    IF v_first_locked OR v_second_locked THEN
        RETURN jsonb_build_object(
            'status', 'error',
            'error_code', 'MANAGER_LOCKED',
            'message', 'One or both managers are currently in an active match.'
        );
    END IF;

    -- Create match run
    v_run_id := gen_random_uuid();
    INSERT INTO public.match_runs (
        id, home_id, away_id, run_type, status, squad_snapshot, created_at
    ) VALUES (
        v_run_id, p_home_id, p_away_id, 'friendly', 'streaming', p_squad_snapshot, NOW()
    );

    -- Insert locks for both managers
    INSERT INTO public.match_locks (discord_id, lock_type, run_id, acquired_at)
    VALUES 
        (p_home_id, 'friendly', v_run_id, NOW()),
        (p_away_id, 'friendly', v_run_id, NOW());

    RETURN jsonb_build_object(
        'status', 'success',
        'run_id', v_run_id
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.start_friendly_match(TEXT, BIGINT, BIGINT, JSONB) TO anon, authenticated, service_role;

-- Migration 108: Match Concurrency & Squad Locking Integrity (Feature 056)

-- 1. Alter match_locks table to add run_id foreign key and UNIQUE constraint on discord_id
ALTER TABLE public.match_locks
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES public.match_runs(id) ON DELETE CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'match_locks_discord_id_key'
    ) THEN
        ALTER TABLE public.match_locks ADD CONSTRAINT match_locks_discord_id_key UNIQUE (discord_id);
    END IF;
END $$;

-- 2. Update assert_not_in_match helper to raise structured P0001 manager_in_active_match exception
CREATE OR REPLACE FUNCTION public.assert_not_in_match(p_discord_id BIGINT)
RETURNS VOID AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.match_locks WHERE discord_id = p_discord_id) THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'manager_in_active_match';
    END IF;
END;
$$ LANGUAGE plpgsql;

GRANT EXECUTE ON FUNCTION public.assert_not_in_match(BIGINT) TO anon, authenticated, service_role;

-- 3. Create RPC assert_manager_match_available
CREATE OR REPLACE FUNCTION public.assert_manager_match_available(
    p_discord_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_lock public.match_locks%ROWTYPE;
BEGIN
    SELECT * INTO v_lock
    FROM public.match_locks
    WHERE discord_id = p_discord_id;

    IF FOUND THEN
        RETURN jsonb_build_object(
            'available', false,
            'lock_type', v_lock.lock_type,
            'run_id', v_lock.run_id,
            'message', 'manager_in_active_match'
        );
    END IF;

    RETURN jsonb_build_object('available', true);
END;
$$;

GRANT EXECUTE ON FUNCTION public.assert_manager_match_available(BIGINT) TO anon, authenticated, service_role;

-- 4. Create RPC start_friendly_match
CREATE OR REPLACE FUNCTION public.start_friendly_match(
    p_challenge_id UUID,
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

GRANT EXECUTE ON FUNCTION public.start_friendly_match(UUID, BIGINT, BIGINT, JSONB) TO anon, authenticated, service_role;

-- 5. Create RPC start_single_manager_match
CREATE OR REPLACE FUNCTION public.start_single_manager_match(
    p_discord_id BIGINT,
    p_run_type TEXT,
    p_squad_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_locked BOOLEAN;
    v_run_id UUID;
BEGIN
    SELECT EXISTS (SELECT 1 FROM public.match_locks WHERE discord_id = p_discord_id FOR UPDATE) INTO v_locked;

    IF v_locked THEN
        RETURN jsonb_build_object(
            'status', 'error',
            'error_code', 'MANAGER_LOCKED',
            'message', 'You are currently in an active match.'
        );
    END IF;

    v_run_id := gen_random_uuid();
    INSERT INTO public.match_runs (
        id, home_id, away_id, run_type, status, squad_snapshot, created_at
    ) VALUES (
        v_run_id, p_discord_id, NULL, p_run_type, 'streaming', p_squad_snapshot, NOW()
    );

    INSERT INTO public.match_locks (discord_id, lock_type, run_id, acquired_at)
    VALUES (p_discord_id, p_run_type, v_run_id, NOW());

    RETURN jsonb_build_object(
        'status', 'success',
        'run_id', v_run_id
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.start_single_manager_match(BIGINT, TEXT, JSONB) TO anon, authenticated, service_role;

-- 6. Update reconcile_orphaned_match_locks to consider streaming, completing, and recovering active
CREATE OR REPLACE FUNCTION public.reconcile_orphaned_match_locks()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_deleted INTEGER := 0;
BEGIN
    WITH to_delete AS (
        SELECT ml.discord_id
        FROM public.match_locks ml
        LEFT JOIN public.match_runs mr ON ml.run_id = mr.id
        WHERE ml.run_id IS NULL OR mr.status IN ('completed', 'abandoned')
    )
    DELETE FROM public.match_locks ml
    USING to_delete td
    WHERE ml.discord_id = td.discord_id;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

GRANT EXECUTE ON FUNCTION public.reconcile_orphaned_match_locks() TO anon, authenticated, service_role;

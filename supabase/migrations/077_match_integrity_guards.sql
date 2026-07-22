-- 077_match_integrity_guards.sql
-- US-42.4: abandon_match_run (status + lock release) + orphan lock reconcile

CREATE OR REPLACE FUNCTION public.abandon_match_run(
    p_run_id UUID,
    p_reason TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_run public.match_runs%ROWTYPE;
    v_id BIGINT;
BEGIN
    SELECT * INTO v_run
    FROM public.match_runs
    WHERE id = p_run_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', FALSE, 'reason', 'not_found');
    END IF;

    IF v_run.status = 'completed' THEN
        FOREACH v_id IN ARRAY ARRAY[
            v_run.home_discord_id,
            v_run.away_discord_id,
            v_run.active_discord_id
        ]
        LOOP
            IF v_id IS NOT NULL AND v_id <> 0 THEN
                PERFORM public.release_match_lock(v_id);
            END IF;
        END LOOP;
        RETURN jsonb_build_object(
            'ok', TRUE,
            'status', 'completed',
            'noop', TRUE,
            'reason', p_reason
        );
    END IF;

    IF v_run.status IN ('abandoned', 'failed') THEN
        FOREACH v_id IN ARRAY ARRAY[
            v_run.home_discord_id,
            v_run.away_discord_id,
            v_run.active_discord_id
        ]
        LOOP
            IF v_id IS NOT NULL AND v_id <> 0 THEN
                PERFORM public.release_match_lock(v_id);
            END IF;
        END LOOP;
        RETURN jsonb_build_object(
            'ok', TRUE,
            'status', v_run.status,
            'noop', TRUE,
            'reason', p_reason
        );
    END IF;

    UPDATE public.match_runs
    SET
        status = 'abandoned',
        completed_at = NOW(),
        updated_at = NOW()
    WHERE id = p_run_id;

    FOREACH v_id IN ARRAY ARRAY[
        v_run.home_discord_id,
        v_run.away_discord_id,
        v_run.active_discord_id
    ]
    LOOP
        IF v_id IS NOT NULL AND v_id <> 0 THEN
            PERFORM public.release_match_lock(v_id);
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'ok', TRUE,
        'status', 'abandoned',
        'noop', FALSE,
        'reason', p_reason
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.reconcile_orphaned_match_locks()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    WITH active_ids AS (
        SELECT home_discord_id AS discord_id
        FROM public.match_runs
        WHERE status IN ('streaming', 'completing')
          AND home_discord_id IS NOT NULL
          AND home_discord_id <> 0
        UNION
        SELECT away_discord_id
        FROM public.match_runs
        WHERE status IN ('streaming', 'completing')
          AND away_discord_id IS NOT NULL
          AND away_discord_id <> 0
        UNION
        SELECT active_discord_id
        FROM public.match_runs
        WHERE status IN ('streaming', 'completing')
          AND active_discord_id IS NOT NULL
          AND active_discord_id <> 0
    )
    DELETE FROM public.match_locks ml
    WHERE NOT EXISTS (
        SELECT 1 FROM active_ids a WHERE a.discord_id = ml.discord_id
    );

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.abandon_match_run(UUID, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.reconcile_orphaned_match_locks()
    TO anon, authenticated, service_role;

DO $$
DECLARE
    missing TEXT := '';
BEGIN
    IF to_regprocedure('public.abandon_match_run(uuid,text)') IS NULL THEN
        missing := missing || 'abandon_match_run ';
    END IF;
    IF to_regprocedure('public.reconcile_orphaned_match_locks()') IS NULL THEN
        missing := missing || 'reconcile_orphaned_match_locks ';
    END IF;
    IF missing <> '' THEN
        RAISE EXCEPTION '077 schema guard failed: %', missing;
    END IF;
END;
$$;

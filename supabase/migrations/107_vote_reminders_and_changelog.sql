-- supabase/migrations/107_vote_reminders_and_changelog.sql
-- Feature 055: Vote Reminders and Deployment Changelog

-- 1) Create topgg_vote_reminders table
CREATE TABLE IF NOT EXISTS public.topgg_vote_reminders (
    discord_user_id       BIGINT PRIMARY KEY,

    last_vote_at          TIMESTAMPTZ NOT NULL,
    next_vote_at          TIMESTAMPTZ NOT NULL,

    reminder_window_key   TEXT NOT NULL,
    reminder_claimed_at   TIMESTAMPTZ,
    reminder_sent_at      TIMESTAMPTZ,

    dm_status              TEXT,
    fallback_pending       BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_created_at    TIMESTAMPTZ,
    fallback_shown_at      TIMESTAMPTZ,

    last_checked_at        TIMESTAMPTZ,
    next_check_at          TIMESTAMPTZ,
    check_failure_count    INTEGER NOT NULL DEFAULT 0,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_topgg_reminder_dm_status
        CHECK (
            dm_status IS NULL OR
            dm_status IN ('sent', 'forbidden', 'failed')
        )
);

-- Index for due reminder queries
CREATE INDEX IF NOT EXISTS idx_topgg_vote_reminders_due
ON public.topgg_vote_reminders (next_check_at)
WHERE reminder_sent_at IS NULL;

-- Enable RLS
ALTER TABLE public.topgg_vote_reminders ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'topgg_vote_reminders'
          AND policyname = 'topgg_vote_reminders_read_anon'
    ) THEN
        CREATE POLICY topgg_vote_reminders_read_anon
            ON public.topgg_vote_reminders
            FOR SELECT TO anon, authenticated, service_role
            USING (true);
    END IF;
END $$;

GRANT ALL ON TABLE public.topgg_vote_reminders TO anon, authenticated, service_role;


-- 2) RPC: claim_due_topgg_vote_reminders
CREATE OR REPLACE FUNCTION public.claim_due_topgg_vote_reminders(
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    discord_user_id     BIGINT,
    reminder_window_key TEXT,
    last_vote_at        TIMESTAMPTZ,
    next_vote_at        TIMESTAMPTZ,
    next_check_at       TIMESTAMPTZ,
    check_failure_count INTEGER
) LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RETURN QUERY
    WITH due_rows AS (
        SELECT r.discord_user_id
        FROM public.topgg_vote_reminders r
        WHERE r.reminder_sent_at IS NULL
          AND r.next_check_at <= NOW()
          AND (r.reminder_claimed_at IS NULL OR r.reminder_claimed_at < NOW() - INTERVAL '15 minutes')
        ORDER BY r.next_check_at ASC
        LIMIT LEAST(p_limit, 100)
        FOR UPDATE SKIP LOCKED
    )
    UPDATE public.topgg_vote_reminders r
    SET reminder_claimed_at = NOW(),
        updated_at = NOW()
    FROM due_rows d
    WHERE r.discord_user_id = d.discord_user_id
    RETURNING
        r.discord_user_id,
        r.reminder_window_key,
        r.last_vote_at,
        r.next_vote_at,
        r.next_check_at,
        r.check_failure_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.claim_due_topgg_vote_reminders(INTEGER) TO anon, authenticated, service_role;


-- 3) RPC: claim_deployment_changelog
CREATE OR REPLACE FUNCTION public.claim_deployment_changelog(
    p_deployment_key TEXT,
    p_instance_id TEXT DEFAULT 'default'
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_rec RECORD;
    v_curr_key TEXT;
    v_claimed_at TIMESTAMPTZ;
BEGIN
    SELECT value_json INTO v_rec FROM public.game_config WHERE key = 'last_changelog_deployment' FOR UPDATE;
    
    IF v_rec IS NOT NULL AND v_rec.value_json IS NOT NULL THEN
        v_curr_key := (v_rec.value_json #>> '{deployment_key}');
        v_claimed_at := (v_rec.value_json #>> '{claimed_at}')::TIMESTAMPTZ;
        
        IF v_curr_key = p_deployment_key AND (v_rec.value_json #>> '{posted_at}') IS NOT NULL THEN
            RETURN jsonb_build_object('status', 'already_posted', 'deployment_key', p_deployment_key);
        END IF;

        IF v_curr_key = p_deployment_key AND v_claimed_at IS NOT NULL AND v_claimed_at > NOW() - INTERVAL '10 minutes' THEN
            RETURN jsonb_build_object('status', 'already_claimed', 'deployment_key', p_deployment_key);
        END IF;
    END IF;

    -- Upsert claim
    INSERT INTO public.game_config (key, value_json)
    VALUES (
        'last_changelog_deployment',
        jsonb_build_object(
            'deployment_key', p_deployment_key,
            'claimed_at', NOW(),
            'instance_id', p_instance_id
        )
    )
    ON CONFLICT (key) DO UPDATE
    SET value_json = EXCLUDED.value_json;

    RETURN jsonb_build_object('status', 'claimed', 'deployment_key', p_deployment_key);
END;
$$;

GRANT EXECUTE ON FUNCTION public.claim_deployment_changelog(TEXT, TEXT) TO anon, authenticated, service_role;


-- 4) RPC: complete_deployment_changelog
CREATE OR REPLACE FUNCTION public.complete_deployment_changelog(
    p_deployment_key TEXT,
    p_version TEXT,
    p_commit TEXT,
    p_channel_id BIGINT
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    UPDATE public.game_config
    SET value_json = jsonb_build_object(
        'deployment_key', p_deployment_key,
        'version', p_version,
        'commit', p_commit,
        'posted_at', NOW(),
        'channel_id', p_channel_id
    )
    WHERE key = 'last_changelog_deployment';

    RETURN jsonb_build_object('status', 'completed', 'deployment_key', p_deployment_key);
END;
$$;

GRANT EXECUTE ON FUNCTION public.complete_deployment_changelog(TEXT, TEXT, TEXT, BIGINT) TO anon, authenticated, service_role;


-- 5) Schema guard block
DO $$
DECLARE
    req TEXT;
    reqs TEXT[] := ARRAY[
        'table:public.topgg_vote_reminders',
        'policy:public.topgg_vote_reminders.topgg_vote_reminders_read_anon',
        'function:public.claim_due_topgg_vote_reminders',
        'function:public.claim_deployment_changelog',
        'function:public.complete_deployment_changelog'
    ];
BEGIN
    FOREACH req IN ARRAY reqs LOOP
        IF split_part(req, ':', 1) = 'table' THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = split_part(split_part(req, ':', 2), '.', 1)
                  AND table_name = split_part(split_part(req, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing table %', req;
            END IF;
        ELSIF split_part(req, ':', 1) = 'function' THEN
            IF NOT EXISTS (
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = split_part(split_part(req, ':', 2), '.', 1)
                  AND p.proname = split_part(split_part(req, ':', 2), '.', 2)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing function %', req;
            END IF;
        ELSIF split_part(req, ':', 1) = 'policy' THEN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = split_part(split_part(req, ':', 2), '.', 1)
                  AND tablename = split_part(split_part(req, ':', 2), '.', 2)
                  AND policyname = split_part(split_part(req, ':', 2), '.', 3)
            ) THEN
                RAISE EXCEPTION 'Schema guard failed: missing policy %', req;
            END IF;
        END IF;
    END LOOP;
END;
$$;

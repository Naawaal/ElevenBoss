-- 109_competitive_bot_match.sql
-- Feature 057: Competitive Bot Match — flags, match_runs.competitive_state,
-- match_history decided_by/pens, player_suspensions + settlement RPCs.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) match_runs competitive snapshot
-- ---------------------------------------------------------------------------
ALTER TABLE public.match_runs
    ADD COLUMN IF NOT EXISTS competitive_state JSONB;

-- ---------------------------------------------------------------------------
-- 2) match_history result extensions
-- ---------------------------------------------------------------------------
ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS decided_by TEXT,
    ADD COLUMN IF NOT EXISTS home_penalties SMALLINT,
    ADD COLUMN IF NOT EXISTS away_penalties SMALLINT;

ALTER TABLE public.match_history DROP CONSTRAINT IF EXISTS match_history_decided_by_check;
ALTER TABLE public.match_history
    ADD CONSTRAINT match_history_decided_by_check
    CHECK (
        decided_by IS NULL
        OR decided_by IN ('regulation', 'extra_time', 'penalties')
    );

-- ---------------------------------------------------------------------------
-- 3) player_suspensions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.player_suspensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_card_id UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    club_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    source_match_run_id UUID NOT NULL,
    matches_total SMALLINT NOT NULL,
    matches_remaining SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    served_at TIMESTAMPTZ,
    CONSTRAINT ck_player_suspensions_reason
        CHECK (reason IN ('second_yellow', 'straight_red')),
    CONSTRAINT ck_player_suspensions_remaining
        CHECK (matches_remaining >= 0 AND matches_remaining <= matches_total)
);

CREATE INDEX IF NOT EXISTS idx_player_suspensions_club_active
    ON public.player_suspensions (club_id)
    WHERE matches_remaining > 0 AND served_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_player_suspensions_card_active
    ON public.player_suspensions (player_card_id)
    WHERE matches_remaining > 0 AND served_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_player_suspensions_run_card
    ON public.player_suspensions (source_match_run_id, player_card_id);

ALTER TABLE public.player_suspensions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'player_suspensions'
          AND policyname = 'player_suspensions_select'
    ) THEN
        CREATE POLICY player_suspensions_select
            ON public.player_suspensions FOR SELECT
            TO anon, authenticated, service_role
            USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'player_suspensions'
          AND policyname = 'player_suspensions_write'
    ) THEN
        CREATE POLICY player_suspensions_write
            ON public.player_suspensions FOR ALL
            TO anon, authenticated, service_role
            USING (true) WITH CHECK (true);
    END IF;
END $$;

GRANT ALL ON TABLE public.player_suspensions TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 4) game_config seeds (flag OFF)
-- ---------------------------------------------------------------------------
INSERT INTO public.game_config (key, value_json) VALUES
    ('competitive_match_enabled', 'false'::jsonb),
    ('competitive_extra_time_fatigue_multiplier', '1.35'::jsonb),
    ('competitive_extra_time_injury_multiplier', '1.25'::jsonb),
    ('bot_dynamic_difficulty_enabled', 'true'::jsonb),
    ('bot_difficulty_rating_offset', '0'::jsonb),
    ('bot_difficulty_min_delta', '-4'::jsonb),
    ('bot_difficulty_max_delta', '4'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5) list_active_suspensions
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.list_active_suspensions(p_club_id BIGINT)
RETURNS TABLE (
    player_card_id UUID,
    reason TEXT,
    matches_remaining SMALLINT,
    matches_total SMALLINT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT s.player_card_id, s.reason, s.matches_remaining, s.matches_total
    FROM public.player_suspensions s
    WHERE s.club_id = p_club_id
      AND s.matches_remaining > 0
      AND s.served_at IS NULL
    ORDER BY s.created_at ASC;
$$;

GRANT EXECUTE ON FUNCTION public.list_active_suspensions(BIGINT) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 6) apply_bot_match_discipline (idempotent per run)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.apply_bot_match_discipline(
    p_run_id UUID,
    p_club_id BIGINT,
    p_dismissals JSONB DEFAULT '[]'::jsonb
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_item JSONB;
    v_card UUID;
    v_reason TEXT;
    v_total SMALLINT;
    v_created INT := 0;
    v_decremented INT := 0;
BEGIN
    IF p_run_id IS NULL OR p_club_id IS NULL THEN
        RAISE EXCEPTION 'apply_bot_match_discipline requires run_id and club_id';
    END IF;

    -- Create suspensions from dismissals (idempotent via unique index)
    FOR v_item IN SELECT * FROM jsonb_array_elements(COALESCE(p_dismissals, '[]'::jsonb))
    LOOP
        v_card := NULLIF(v_item->>'player_card_id', '')::UUID;
        v_reason := COALESCE(v_item->>'reason', '');
        IF v_card IS NULL THEN
            CONTINUE;
        END IF;
        IF v_reason = 'straight_red' THEN
            v_total := 2;
        ELSIF v_reason = 'second_yellow' THEN
            v_total := 1;
        ELSE
            CONTINUE;
        END IF;

        INSERT INTO public.player_suspensions (
            player_card_id, club_id, reason, source_match_run_id,
            matches_total, matches_remaining
        ) VALUES (
            v_card, p_club_id, v_reason, p_run_id, v_total, v_total
        )
        ON CONFLICT (source_match_run_id, player_card_id) DO NOTHING;

        IF FOUND THEN
            v_created := v_created + 1;
        END IF;
    END LOOP;

    -- Serve one Bot Battle for existing active suspensions of this club
    -- Skip rows created from THIS run (they start after this match)
    UPDATE public.player_suspensions s
    SET
        matches_remaining = s.matches_remaining - 1,
        served_at = CASE WHEN s.matches_remaining - 1 <= 0 THEN NOW() ELSE s.served_at END
    WHERE s.club_id = p_club_id
      AND s.matches_remaining > 0
      AND s.served_at IS NULL
      AND s.source_match_run_id IS DISTINCT FROM p_run_id;

    GET DIAGNOSTICS v_decremented = ROW_COUNT;

    RETURN jsonb_build_object(
        'status', 'ok',
        'created', v_created,
        'decremented', v_decremented
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.apply_bot_match_discipline(UUID, BIGINT, JSONB)
    TO anon, authenticated, service_role;

-- Fix migration 109 guard: simplify column checks
DO $$
BEGIN
    IF to_regclass('public.player_suspensions') IS NULL THEN
        RAISE EXCEPTION '109 guard missing table player_suspensions';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'match_runs'
          AND column_name = 'competitive_state'
    ) THEN
        RAISE EXCEPTION '109 guard missing match_runs.competitive_state';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'match_history'
          AND column_name = 'decided_by'
    ) THEN
        RAISE EXCEPTION '109 guard missing match_history.decided_by';
    END IF;
    IF to_regprocedure('public.list_active_suspensions(bigint)') IS NULL THEN
        RAISE EXCEPTION '109 guard missing list_active_suspensions';
    END IF;
    IF to_regprocedure('public.apply_bot_match_discipline(uuid,bigint,jsonb)') IS NULL THEN
        RAISE EXCEPTION '109 guard missing apply_bot_match_discipline';
    END IF;
END;
$$;

COMMIT;

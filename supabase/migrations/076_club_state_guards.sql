-- 076: US-42.3 Club State Machine
-- assert_club_action_allowed + register_league_season (atomic V1 join).
-- Soft lifecycle columns/RPCs remain 074 (30/90 days — keep in sync with identity.py).

-- ---------------------------------------------------------------------------
-- assert_club_action_allowed
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.assert_club_action_allowed(
    p_club_id BIGINT,
    p_action TEXT
) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_is_ai BOOLEAN;
    v_status TEXT;
    v_last TIMESTAMPTZ;
    v_days NUMERIC;
    v_inactive_days CONSTANT INTEGER := 30;  -- sync identity.py INACTIVE_DAYS
    v_abandoned_days CONSTANT INTEGER := 90; -- sync identity.py ABANDONED_DAYS
    v_soft TEXT;
BEGIN
    IF p_action IS NULL OR btrim(p_action) = '' THEN
        RAISE EXCEPTION 'CLUB_STATE: missing action';
    END IF;

    SELECT COALESCE(is_ai, FALSE), identity_status, last_qualifying_activity_at
    INTO v_is_ai, v_status, v_last
    FROM public.players
    WHERE discord_id = p_club_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Club not found';
    END IF;

    IF v_is_ai AND p_action IN (
        'store_faucet', 'development_mutate', 'squad_mutate', 'market_mutate',
        'match_start', 'league_join', 'recover'
    ) THEN
        RAISE EXCEPTION 'CLUB_STATE: AI blocks %', p_action;
    END IF;

    -- Refresh soft label (same math as classify_club_identity_status)
    IF NOT v_is_ai THEN
        v_days := EXTRACT(EPOCH FROM (NOW() - v_last)) / 86400.0;
        IF v_days >= v_abandoned_days THEN
            v_soft := 'abandoned';
        ELSIF v_days >= v_inactive_days THEN
            v_soft := 'inactive';
        ELSE
            v_soft := 'active';
        END IF;

        IF v_soft IS DISTINCT FROM v_status THEN
            UPDATE public.players
            SET
                identity_status = v_soft,
                identity_status_changed_at = NOW()
            WHERE discord_id = p_club_id;
            v_status := v_soft;
        END IF;
    END IF;

    IF p_action = 'view_hub' THEN
        RETURN;
    END IF;

    -- MatchLocked: mutations Block; store_faucet + recover Allowed
    IF p_action IN (
        'development_mutate', 'squad_mutate', 'market_mutate',
        'match_start', 'league_join'
    ) THEN
        PERFORM public.assert_not_in_match(p_club_id);
    END IF;

    IF p_action = 'league_join' THEN
        IF v_status IN ('inactive', 'abandoned') THEN
            RAISE EXCEPTION 'CLUB_STATE: % blocks league_join',
                initcap(v_status);
        END IF;
        RETURN;
    END IF;

    IF p_action = 'recover' THEN
        IF v_status NOT IN ('inactive', 'abandoned') THEN
            RAISE EXCEPTION 'CLUB_STATE: Active blocks recover';
        END IF;
        RETURN;
    END IF;

    -- store / development / squad / market / match_start: soft Allow
    IF p_action IN (
        'store_faucet', 'development_mutate', 'squad_mutate',
        'market_mutate', 'match_start', 'league_remain'
    ) THEN
        RETURN;
    END IF;

    RAISE EXCEPTION 'CLUB_STATE: unknown action %', p_action;
END;
$$;

-- ---------------------------------------------------------------------------
-- register_league_season — atomic V1 seasonal join
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.register_league_season(
    p_player_id BIGINT,
    p_guild_id BIGINT,
    p_season_id UUID,
    p_eligibility JSONB DEFAULT '{}'::jsonb
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_league_id UUID;
    v_season RECORD;
    v_existing TEXT;
    v_min_matches INTEGER;
    v_min_days INTEGER;
    v_played INTEGER;
    v_created TIMESTAMPTZ;
    v_age_days INTEGER;
    v_snapshot JSONB;
BEGIN
    PERFORM public.assert_club_action_allowed(p_player_id, 'league_join');

    SELECT id INTO v_league_id
    FROM public.leagues
    WHERE guild_id = p_guild_id;

    IF v_league_id IS NULL THEN
        RAISE EXCEPTION 'League not found for guild';
    END IF;

    SELECT s.id, s.status, s.pacing_mode, s.league_id
    INTO v_season
    FROM public.league_seasons s
    WHERE s.id = p_season_id
    FOR UPDATE;

    IF v_season.id IS NULL THEN
        RAISE EXCEPTION 'Season not found';
    END IF;
    IF v_season.league_id IS DISTINCT FROM v_league_id THEN
        RAISE EXCEPTION 'Season does not belong to this guild league';
    END IF;
    IF v_season.pacing_mode IS DISTINCT FROM 'lifecycle_v1' THEN
        RAISE EXCEPTION 'Season is not lifecycle_v1';
    END IF;
    IF v_season.status NOT IN ('registration', 'registration_open') THEN
        RAISE EXCEPTION 'Season registration is closed';
    END IF;

    SELECT status INTO v_existing
    FROM public.league_registrations
    WHERE season_id = p_season_id AND player_id = p_player_id
    FOR UPDATE;

    IF v_existing IN ('registered', 'locked') THEN
        RETURN jsonb_build_object(
            'status', v_existing,
            'season_id', p_season_id,
            'player_id', p_player_id,
            'already_seated', TRUE
        );
    END IF;

    -- Eligibility (same defaults as league_cog._league_join_limits)
    v_min_matches := public.get_game_config_int('league_join_min_matches', 10)::INTEGER;
    v_min_days := public.get_game_config_int('league_join_min_account_days', 7)::INTEGER;

    SELECT matches_played, created_at
    INTO v_played, v_created
    FROM public.players
    WHERE discord_id = p_player_id;

    v_played := COALESCE(v_played, 0);
    v_age_days := GREATEST(
        0,
        FLOOR(EXTRACT(EPOCH FROM (NOW() - COALESCE(v_created, NOW()))) / 86400.0)::INTEGER
    );

    IF v_played < v_min_matches THEN
        RAISE EXCEPTION
            'League registration requires % career matches (you have %)',
            v_min_matches, v_played;
    END IF;
    IF v_age_days < v_min_days THEN
        RAISE EXCEPTION
            'League registration requires a club at least % days old',
            v_min_days;
    END IF;

    v_snapshot := COALESCE(p_eligibility, '{}'::jsonb)
        || jsonb_build_object(
            'matches_played', v_played,
            'account_age_days', v_age_days
        );

    INSERT INTO public.league_members (guild_id, player_id)
    VALUES (p_guild_id, p_player_id)
    ON CONFLICT (guild_id, player_id) DO NOTHING;

    INSERT INTO public.league_registrations (
        season_id, player_id, status, eligibility_snapshot
    ) VALUES (
        p_season_id, p_player_id, 'registered', v_snapshot
    )
    ON CONFLICT (season_id, player_id) DO UPDATE
    SET
        status = CASE
            WHEN public.league_registrations.status IN ('registered', 'locked')
                THEN public.league_registrations.status
            ELSE 'registered'
        END,
        eligibility_snapshot = CASE
            WHEN public.league_registrations.status IN ('registered', 'locked')
                THEN public.league_registrations.eligibility_snapshot
            ELSE EXCLUDED.eligibility_snapshot
        END;

    SELECT status INTO v_existing
    FROM public.league_registrations
    WHERE season_id = p_season_id AND player_id = p_player_id;

    PERFORM public.touch_club_activity(p_player_id);

    RETURN jsonb_build_object(
        'status', COALESCE(v_existing, 'registered'),
        'season_id', p_season_id,
        'player_id', p_player_id,
        'already_seated', FALSE
    );
END;
$$;

-- Permanent / legacy membership join (no open V1 season)
CREATE OR REPLACE FUNCTION public.register_league_membership(
    p_player_id BIGINT,
    p_guild_id BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM public.assert_club_action_allowed(p_player_id, 'league_join');

    IF EXISTS (
        SELECT 1 FROM public.league_members
        WHERE guild_id = p_guild_id AND player_id = p_player_id
    ) THEN
        RETURN jsonb_build_object(
            'guild_id', p_guild_id,
            'player_id', p_player_id,
            'already_seated', TRUE
        );
    END IF;

    INSERT INTO public.league_members (guild_id, player_id)
    VALUES (p_guild_id, p_player_id);

    PERFORM public.touch_club_activity(p_player_id);

    RETURN jsonb_build_object(
        'guild_id', p_guild_id,
        'player_id', p_player_id,
        'already_seated', FALSE
    );
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.assert_club_action_allowed(BIGINT, TEXT)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.register_league_season(BIGINT, BIGINT, UUID, JSONB)
    TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON FUNCTION public.register_league_membership(BIGINT, BIGINT)
    TO anon, authenticated, service_role;

DO $$
DECLARE
    missing TEXT := '';
BEGIN
    IF to_regprocedure('public.assert_club_action_allowed(bigint,text)') IS NULL THEN
        missing := missing || 'assert_club_action_allowed ';
    END IF;
    IF to_regprocedure('public.register_league_season(bigint,bigint,uuid,jsonb)') IS NULL THEN
        missing := missing || 'register_league_season ';
    END IF;
    IF to_regprocedure('public.register_league_membership(bigint,bigint)') IS NULL THEN
        missing := missing || 'register_league_membership ';
    END IF;
    IF missing <> '' THEN
        RAISE EXCEPTION '076 schema guard failed: %', missing;
    END IF;
END;
$$;

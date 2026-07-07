-- US-26: Immersive League Mode v2 — schema, RLS, season prizes

-- ---------------------------------------------------------------------------
-- league_seasons: config + extended status
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS config_json JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.league_seasons DROP CONSTRAINT IF EXISTS league_seasons_status_check;
ALTER TABLE public.league_seasons
    ADD CONSTRAINT league_seasons_status_check
    CHECK (status IN ('registration', 'active', 'paused', 'completed'));

-- ---------------------------------------------------------------------------
-- Awards & history
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_season_awards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    award_type TEXT NOT NULL,
    coin_amount INTEGER NOT NULL DEFAULT 0,
    finish_position INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (season_id, player_id, award_type)
);

CREATE TABLE IF NOT EXISTS public.player_league_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    guild_id BIGINT NOT NULL,
    finish_position INTEGER NOT NULL,
    season_points INTEGER NOT NULL DEFAULT 0,
    goals_for INTEGER NOT NULL DEFAULT 0,
    awards_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_player_league_history_player ON public.player_league_history(player_id);

-- Matchday milestone tracking (weekly pts inside a season)
CREATE TABLE IF NOT EXISTS public.league_matchday_milestones (
    season_id UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    matchday INTEGER NOT NULL,
    points_earned INTEGER NOT NULL DEFAULT 0,
    milestone_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (season_id, player_id, matchday)
);

GRANT ALL ON public.league_season_awards TO anon, authenticated, service_role;
GRANT ALL ON public.player_league_history TO anon, authenticated, service_role;
GRANT ALL ON public.league_matchday_milestones TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- game_config league tunables
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('league_default_size', '8'),
    ('league_min_humans', '2'),
    ('league_registration_hours', '72'),
    ('league_window_hours', '48'),
    ('league_bot_fill_enabled', 'true'),
    ('league_ovr_cap', 'null'),
    ('league_season_prize_pool_base', '5000'),
    ('league_participation_coins', '200'),
    ('league_milestone_pts_threshold', '6'),
    ('league_milestone_bonus_coins', '150'),
    ('league_familiarity_bonus_pct', '2'),
    ('league_familiarity_min_matchdays', '3')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- distribute_season_prizes RPC
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.distribute_season_prizes(p_season_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_pool INT;
    v_participation INT;
    v_guild_id BIGINT;
    v_rec RECORD;
    v_pos INT := 0;
    v_coins INT;
    v_award TEXT;
    v_awards JSONB := '[]'::jsonb;
BEGIN
    SELECT COALESCE((SELECT (value_json #>> '{}')::int FROM game_config WHERE key = 'league_season_prize_pool_base'), 5000)
    INTO v_pool;
    SELECT COALESCE((SELECT (value_json #>> '{}')::int FROM game_config WHERE key = 'league_participation_coins'), 200)
    INTO v_participation;

    SELECT l.guild_id INTO v_guild_id
    FROM league_seasons ls
    JOIN leagues l ON l.id = ls.league_id
    WHERE ls.id = p_season_id;

    FOR v_rec IN
        WITH standings AS (
            SELECT
                lp.player_id,
                p.is_ai,
                SUM(CASE
                    WHEN lf.home_team_id = lp.player_id AND lf.home_score > lf.away_score THEN 3
                    WHEN lf.away_team_id = lp.player_id AND lf.away_score > lf.home_score THEN 3
                    WHEN lf.home_score = lf.away_score AND lp.player_id IN (lf.home_team_id, lf.away_team_id) THEN 1
                    ELSE 0
                END) AS pts,
                SUM(CASE WHEN lf.home_team_id = lp.player_id THEN lf.home_score - lf.away_score
                         WHEN lf.away_team_id = lp.player_id THEN lf.away_score - lf.home_score ELSE 0 END) AS gd,
                SUM(CASE WHEN lf.home_team_id = lp.player_id THEN lf.home_score
                         WHEN lf.away_team_id = lp.player_id THEN lf.away_score ELSE 0 END) AS gf
            FROM league_participants lp
            JOIN players p ON p.discord_id = lp.player_id
            LEFT JOIN league_fixtures lf ON lf.season_id = lp.season_id
                AND lf.is_played = TRUE
                AND lp.player_id IN (lf.home_team_id, lf.away_team_id)
            WHERE lp.season_id = p_season_id AND lp.is_active = TRUE
            GROUP BY lp.player_id, p.is_ai
        )
        SELECT player_id, pts, gd, gf
        FROM standings
        WHERE is_ai = FALSE
        ORDER BY pts DESC, gd DESC, gf DESC, player_id
    LOOP
        v_pos := v_pos + 1;
        IF v_pos = 1 THEN
            v_coins := (v_pool * 60) / 100;
            v_award := 'champion';
        ELSIF v_pos = 2 THEN
            v_coins := (v_pool * 25) / 100;
            v_award := 'runner_up';
        ELSIF v_pos = 3 THEN
            v_coins := (v_pool * 10) / 100;
            v_award := 'third';
        ELSE
            v_coins := v_participation;
            v_award := 'participation';
        END IF;

        INSERT INTO league_season_awards (season_id, player_id, award_type, coin_amount, finish_position)
        VALUES (p_season_id, v_rec.player_id, v_award, v_coins, v_pos)
        ON CONFLICT (season_id, player_id, award_type) DO NOTHING;

        INSERT INTO player_league_history (player_id, season_id, guild_id, finish_position, season_points, goals_for, awards_json)
        VALUES (v_rec.player_id, p_season_id, v_guild_id, v_pos, v_rec.pts, v_rec.gf,
                jsonb_build_array(jsonb_build_object('type', v_award, 'coins', v_coins)))
        ON CONFLICT (player_id, season_id) DO UPDATE SET
            finish_position = EXCLUDED.finish_position,
            season_points = EXCLUDED.season_points,
            goals_for = EXCLUDED.goals_for,
            awards_json = EXCLUDED.awards_json;

        IF v_coins > 0 THEN
            PERFORM apply_club_economy(
                v_rec.player_id,
                v_coins,
                0,
                'league_season_prize',
                'season_prize:' || p_season_id::text || ':' || v_rec.player_id::text,
                jsonb_build_object('season_id', p_season_id, 'position', v_pos, 'award', v_award)
            );
        END IF;

        v_awards := v_awards || jsonb_build_object(
            'player_id', v_rec.player_id, 'position', v_pos, 'award', v_award, 'coins', v_coins
        );
    END LOOP;

    RETURN jsonb_build_object('season_id', p_season_id, 'awards', v_awards);
END;
$$;

GRANT EXECUTE ON FUNCTION public.distribute_season_prizes(UUID) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- RLS policies (bot uses anon key)
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_fixtures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_season_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_season_awards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_league_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.league_matchday_milestones ENABLE ROW LEVEL SECURITY;

DO $policies$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'league_seasons', 'league_participants', 'league_fixtures',
        'match_logs', 'player_season_stats', 'league_season_awards',
        'player_league_history', 'league_matchday_milestones'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I_select ON public.%I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_insert ON public.%I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_update ON public.%I', t, t);
        EXECUTE format(
            'CREATE POLICY %I_select ON public.%I FOR SELECT TO anon, authenticated, service_role USING (true)',
            t, t
        );
        EXECUTE format(
            'CREATE POLICY %I_insert ON public.%I FOR INSERT TO anon, authenticated, service_role WITH CHECK (true)',
            t, t
        );
        EXECUTE format(
            'CREATE POLICY %I_update ON public.%I FOR UPDATE TO anon, authenticated, service_role USING (true) WITH CHECK (true)',
            t, t
        );
    END LOOP;
END $policies$;

-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('table:public.league_season_awards'),
            ('table:public.player_league_history'),
            ('table:public.league_matchday_milestones'),
            ('column:public.league_seasons.config_json'),
            ('function:public.distribute_season_prizes'),
            ('policy:public.league_fixtures.league_fixtures_select'),
            ('policy:public.league_seasons.league_seasons_select'),
            ('policy:public.league_participants.league_participants_select'),
            ('policy:public.match_logs.match_logs_select'),
            ('policy:public.player_season_stats.player_season_stats_select')
    ) AS req(obj)
    WHERE NOT EXISTS (
        SELECT 1 FROM (
            SELECT 'table:' || c.relnamespace::regnamespace::text || '.' || c.relname AS obj
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = 'public'
            UNION ALL
            SELECT 'column:' || table_schema || '.' || table_name || '.' || column_name
            FROM information_schema.columns WHERE table_schema = 'public'
            UNION ALL
            SELECT 'function:public.' || p.proname
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
            UNION ALL
            SELECT 'policy:public.' || tablename || '.' || policyname
            FROM pg_policies WHERE schemaname = 'public'
        ) existing WHERE existing.obj = req.obj
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

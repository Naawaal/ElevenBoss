-- 064: League Dynamics (pacing mode, division tiers, MoMD, seasonal promo/releg)
-- Spec: specs/020-league-dynamics/

-- ---------------------------------------------------------------------------
-- Schema alterations
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_seasons
    ADD COLUMN IF NOT EXISTS pacing_mode TEXT NOT NULL DEFAULT 'legacy';

UPDATE public.league_seasons
SET pacing_mode = 'legacy'
WHERE pacing_mode IS NULL
   OR pacing_mode NOT IN ('legacy', 'dynamics');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'league_seasons_pacing_mode_check'
    ) THEN
        ALTER TABLE public.league_seasons
            ADD CONSTRAINT league_seasons_pacing_mode_check
            CHECK (pacing_mode IN ('legacy', 'dynamics'));
    END IF;
END $$;

ALTER TABLE public.league_participants
    ADD COLUMN IF NOT EXISTS division_tier INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS league_participants_season_division_tier_idx
    ON public.league_participants (season_id, division_tier);

ALTER TABLE public.league_fixtures
    ADD COLUMN IF NOT EXISTS resolved_by TEXT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'league_fixtures_resolved_by_check'
    ) THEN
        ALTER TABLE public.league_fixtures
            ADD CONSTRAINT league_fixtures_resolved_by_check
            CHECK (resolved_by IS NULL OR resolved_by IN ('manual', 'auto_sim'));
    END IF;
END $$;

ALTER TABLE public.league_members
    ADD COLUMN IF NOT EXISTS seasonal_division_tier INTEGER NOT NULL DEFAULT 1;

-- ---------------------------------------------------------------------------
-- Manager of the Matchday awards
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.league_matchday_manager_awards (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id     UUID NOT NULL REFERENCES public.league_seasons(id) ON DELETE CASCADE,
    matchday      INTEGER NOT NULL,
    player_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE RESTRICT,
    fixture_id    UUID NOT NULL REFERENCES public.league_fixtures(id) ON DELETE RESTRICT,
    margin        INTEGER NOT NULL,
    goals_for     INTEGER NOT NULL,
    coins_awarded BIGINT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (season_id, matchday)
);

CREATE INDEX IF NOT EXISTS league_matchday_manager_awards_season_matchday_idx
    ON public.league_matchday_manager_awards (season_id, matchday);

CREATE INDEX IF NOT EXISTS league_matchday_manager_awards_player_created_idx
    ON public.league_matchday_manager_awards (player_id, created_at DESC);

ALTER TABLE public.league_matchday_manager_awards ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS league_matchday_manager_awards_select
    ON public.league_matchday_manager_awards;
DROP POLICY IF EXISTS league_matchday_manager_awards_insert
    ON public.league_matchday_manager_awards;

CREATE POLICY league_matchday_manager_awards_select
    ON public.league_matchday_manager_awards
    FOR SELECT
    TO anon, authenticated, service_role
    USING (true);

CREATE POLICY league_matchday_manager_awards_insert
    ON public.league_matchday_manager_awards
    FOR INSERT
    TO anon, authenticated, service_role
    WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE public.league_matchday_manager_awards
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Game config seeds
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('league_dynamics_enabled', 'false'),
    ('league_momd_coins', '2000'),
    ('league_dynamics_clubs_per_division', '8'),
    ('league_dynamics_promo_spots', '2'),
    ('league_dynamics_default_duration_days', '14')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Helper: league_dynamics_enabled
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.league_dynamics_enabled()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        (public.get_game_config('league_dynamics_enabled') #>> '{}')::BOOLEAN,
        FALSE
    );
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.league_dynamics_enabled()
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- RPC: award_manager_of_the_matchday
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.award_manager_of_the_matchday(
    p_season_id UUID,
    p_matchday INTEGER
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_existing RECORD;
    v_winner RECORD;
    v_coins BIGINT;
    v_unplayed INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.league_seasons WHERE id = p_season_id) THEN
        RAISE EXCEPTION 'Season not found';
    END IF;

    SELECT COUNT(*)::INT INTO v_unplayed
    FROM public.league_fixtures
    WHERE season_id = p_season_id
      AND matchday = p_matchday
      AND is_played = FALSE;

    IF v_unplayed > 0 THEN
        RETURN jsonb_build_object('status', 'pending');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.league_fixtures
        WHERE season_id = p_season_id
          AND matchday = p_matchday
    ) THEN
        RETURN jsonb_build_object('status', 'pending');
    END IF;

    SELECT *
    INTO v_existing
    FROM public.league_matchday_manager_awards
    WHERE season_id = p_season_id
      AND matchday = p_matchday;

    IF FOUND THEN
        RETURN jsonb_build_object(
            'status', 'already_awarded',
            'player_id', v_existing.player_id,
            'fixture_id', v_existing.fixture_id,
            'margin', v_existing.margin,
            'coins', v_existing.coins_awarded
        );
    END IF;

    SELECT
        CASE
            WHEN lf.home_score > lf.away_score THEN lf.home_team_id
            ELSE lf.away_team_id
        END AS player_id,
        lf.id AS fixture_id,
        ABS(lf.home_score - lf.away_score) AS margin,
        CASE
            WHEN lf.home_score > lf.away_score THEN lf.home_score
            ELSE lf.away_score
        END AS goals_for
    INTO v_winner
    FROM public.league_fixtures lf
    JOIN public.players ph ON ph.discord_id = lf.home_team_id
    JOIN public.players pa ON pa.discord_id = lf.away_team_id
    WHERE lf.season_id = p_season_id
      AND lf.matchday = p_matchday
      AND lf.is_played = TRUE
      AND lf.resolved_by = 'manual'
      AND lf.home_score IS NOT NULL
      AND lf.away_score IS NOT NULL
      AND lf.home_score <> lf.away_score
      AND (
          (lf.home_score > lf.away_score AND COALESCE(ph.is_ai, FALSE) = FALSE)
          OR
          (lf.away_score > lf.home_score AND COALESCE(pa.is_ai, FALSE) = FALSE)
      )
    ORDER BY
        ABS(lf.home_score - lf.away_score) DESC,
        CASE
            WHEN lf.home_score > lf.away_score THEN lf.home_score
            ELSE lf.away_score
        END DESC,
        CASE
            WHEN lf.home_score > lf.away_score THEN lf.home_team_id
            ELSE lf.away_team_id
        END ASC
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('status', 'no_eligible');
    END IF;

    v_coins := public.get_game_config_int('league_momd_coins', 2000);

    PERFORM public.apply_club_economy(
        v_winner.player_id,
        v_coins,
        0,
        'league_momd',
        'momd:' || p_season_id::text || ':' || p_matchday::text,
        jsonb_build_object(
            'season_id', p_season_id,
            'matchday', p_matchday,
            'fixture_id', v_winner.fixture_id,
            'margin', v_winner.margin,
            'goals_for', v_winner.goals_for
        )
    );

    INSERT INTO public.league_matchday_manager_awards (
        season_id, matchday, player_id, fixture_id, margin, goals_for, coins_awarded
    ) VALUES (
        p_season_id,
        p_matchday,
        v_winner.player_id,
        v_winner.fixture_id,
        v_winner.margin,
        v_winner.goals_for,
        v_coins
    )
    ON CONFLICT (season_id, matchday) DO NOTHING;

    SELECT *
    INTO v_existing
    FROM public.league_matchday_manager_awards
    WHERE season_id = p_season_id
      AND matchday = p_matchday;

    IF v_existing.player_id = v_winner.player_id
       AND v_existing.fixture_id = v_winner.fixture_id THEN
        RETURN jsonb_build_object(
            'status', 'awarded',
            'player_id', v_existing.player_id,
            'fixture_id', v_existing.fixture_id,
            'margin', v_existing.margin,
            'coins', v_existing.coins_awarded
        );
    END IF;

    RETURN jsonb_build_object(
        'status', 'already_awarded',
        'player_id', v_existing.player_id,
        'fixture_id', v_existing.fixture_id,
        'margin', v_existing.margin,
        'coins', v_existing.coins_awarded
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.award_manager_of_the_matchday(UUID, INTEGER)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- RPC: apply_seasonal_promotion_relegation
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.apply_seasonal_promotion_relegation(
    p_season_id UUID
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_season RECORD;
    v_guild_id BIGINT;
    v_spots INT;
    v_tier INT;
    v_max_tier INT;
    v_n_upper INT;
    v_n_lower INT;
    v_k_upper INT;
    v_k_lower INT;
    v_moves JSONB := '[]'::jsonb;
    v_player_id BIGINT;
BEGIN
    SELECT ls.*
    INTO v_season
    FROM public.league_seasons ls
    WHERE ls.id = p_season_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Season not found';
    END IF;

    IF COALESCE(v_season.pacing_mode, 'legacy') <> 'dynamics' THEN
        RETURN jsonb_build_object(
            'status', 'skipped_legacy',
            'season_id', p_season_id,
            'moves', '[]'::jsonb
        );
    END IF;

    IF COALESCE(v_season.config_json->>'promo_applied', 'false') = 'true' THEN
        RETURN jsonb_build_object(
            'status', 'already_applied',
            'season_id', p_season_id,
            'moves', '[]'::jsonb
        );
    END IF;

    SELECT l.guild_id INTO v_guild_id
    FROM public.leagues l
    WHERE l.id = v_season.league_id;

    IF v_guild_id IS NULL THEN
        RAISE EXCEPTION 'League guild not found for season';
    END IF;

    v_spots := public.get_game_config_int('league_dynamics_promo_spots', 2)::INT;
    IF v_spots < 1 THEN
        v_spots := 2;
    END IF;

    SELECT COALESCE(MAX(lp.division_tier), 1)
    INTO v_max_tier
    FROM public.league_participants lp
    WHERE lp.season_id = p_season_id
      AND lp.is_active = TRUE;

    FOR v_tier IN 1..(v_max_tier - 1) LOOP
        WITH standings AS (
            SELECT
                lp.player_id,
                lp.division_tier,
                p.is_ai,
                SUM(CASE
                    WHEN lf.home_team_id = lp.player_id AND lf.home_score > lf.away_score THEN 3
                    WHEN lf.away_team_id = lp.player_id AND lf.away_score > lf.home_score THEN 3
                    WHEN lf.home_score = lf.away_score
                         AND lp.player_id IN (lf.home_team_id, lf.away_team_id) THEN 1
                    ELSE 0
                END) AS pts,
                SUM(CASE
                    WHEN lf.home_team_id = lp.player_id THEN lf.home_score - lf.away_score
                    WHEN lf.away_team_id = lp.player_id THEN lf.away_score - lf.home_score
                    ELSE 0
                END) AS gd,
                SUM(CASE
                    WHEN lf.home_team_id = lp.player_id THEN lf.home_score
                    WHEN lf.away_team_id = lp.player_id THEN lf.away_score
                    ELSE 0
                END) AS gf
            FROM public.league_participants lp
            JOIN public.players p ON p.discord_id = lp.player_id
            LEFT JOIN public.league_fixtures lf ON lf.season_id = lp.season_id
                AND lf.is_played = TRUE
                AND lp.player_id IN (lf.home_team_id, lf.away_team_id)
            WHERE lp.season_id = p_season_id
              AND lp.is_active = TRUE
              AND lp.division_tier IN (v_tier, v_tier + 1)
            GROUP BY lp.player_id, lp.division_tier, p.is_ai
        ),
        ranked AS (
            SELECT
                player_id,
                division_tier,
                ROW_NUMBER() OVER (
                    PARTITION BY division_tier
                    ORDER BY pts DESC, gd DESC, gf DESC, player_id ASC
                ) AS rn_asc,
                COUNT(*) OVER (PARTITION BY division_tier) AS n_humans
            FROM standings
            WHERE is_ai = FALSE
        )
        SELECT
            COALESCE(MAX(CASE WHEN division_tier = v_tier THEN n_humans END), 0),
            COALESCE(MAX(CASE WHEN division_tier = v_tier + 1 THEN n_humans END), 0)
        INTO v_n_upper, v_n_lower
        FROM ranked;

        -- Skip adjacent pair when either human table is too small
        IF v_n_upper < 4 OR v_n_lower < 4 THEN
            CONTINUE;
        END IF;

        v_k_upper := LEAST(v_spots, v_n_upper / 2);
        v_k_lower := LEAST(v_spots, v_n_lower / 2);
        IF (2 * v_k_upper) > v_n_upper THEN
            v_k_upper := 1;
        END IF;
        IF (2 * v_k_lower) > v_n_lower THEN
            v_k_lower := 1;
        END IF;

        -- Relegate bottom of tier t → t+1
        FOR v_player_id IN
            WITH standings AS (
                SELECT
                    lp.player_id,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id AND lf.home_score > lf.away_score THEN 3
                        WHEN lf.away_team_id = lp.player_id AND lf.away_score > lf.home_score THEN 3
                        WHEN lf.home_score = lf.away_score
                             AND lp.player_id IN (lf.home_team_id, lf.away_team_id) THEN 1
                        ELSE 0
                    END) AS pts,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id THEN lf.home_score - lf.away_score
                        WHEN lf.away_team_id = lp.player_id THEN lf.away_score - lf.home_score
                        ELSE 0
                    END) AS gd,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id THEN lf.home_score
                        WHEN lf.away_team_id = lp.player_id THEN lf.away_score
                        ELSE 0
                    END) AS gf
                FROM public.league_participants lp
                JOIN public.players p ON p.discord_id = lp.player_id
                LEFT JOIN public.league_fixtures lf ON lf.season_id = lp.season_id
                    AND lf.is_played = TRUE
                    AND lp.player_id IN (lf.home_team_id, lf.away_team_id)
                WHERE lp.season_id = p_season_id
                  AND lp.is_active = TRUE
                  AND lp.division_tier = v_tier
                  AND p.is_ai = FALSE
                GROUP BY lp.player_id
            ),
            ordered AS (
                SELECT
                    player_id,
                    ROW_NUMBER() OVER (ORDER BY pts DESC, gd DESC, gf DESC, player_id ASC) AS rn
                FROM standings
            )
            SELECT player_id
            FROM ordered
            WHERE rn > (v_n_upper - v_k_upper)
            ORDER BY rn
        LOOP
            UPDATE public.league_members
            SET seasonal_division_tier = v_tier + 1
            WHERE guild_id = v_guild_id
              AND player_id = v_player_id;

            v_moves := v_moves || jsonb_build_object(
                'player_id', v_player_id,
                'from_tier', v_tier,
                'to_tier', v_tier + 1,
                'kind', 'relegation'
            );
        END LOOP;

        -- Promote top of tier t+1 → t
        FOR v_player_id IN
            WITH standings AS (
                SELECT
                    lp.player_id,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id AND lf.home_score > lf.away_score THEN 3
                        WHEN lf.away_team_id = lp.player_id AND lf.away_score > lf.home_score THEN 3
                        WHEN lf.home_score = lf.away_score
                             AND lp.player_id IN (lf.home_team_id, lf.away_team_id) THEN 1
                        ELSE 0
                    END) AS pts,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id THEN lf.home_score - lf.away_score
                        WHEN lf.away_team_id = lp.player_id THEN lf.away_score - lf.home_score
                        ELSE 0
                    END) AS gd,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id THEN lf.home_score
                        WHEN lf.away_team_id = lp.player_id THEN lf.away_score
                        ELSE 0
                    END) AS gf
                FROM public.league_participants lp
                JOIN public.players p ON p.discord_id = lp.player_id
                LEFT JOIN public.league_fixtures lf ON lf.season_id = lp.season_id
                    AND lf.is_played = TRUE
                    AND lp.player_id IN (lf.home_team_id, lf.away_team_id)
                WHERE lp.season_id = p_season_id
                  AND lp.is_active = TRUE
                  AND lp.division_tier = v_tier + 1
                  AND p.is_ai = FALSE
                GROUP BY lp.player_id
            ),
            ordered AS (
                SELECT
                    player_id,
                    ROW_NUMBER() OVER (ORDER BY pts DESC, gd DESC, gf DESC, player_id ASC) AS rn
                FROM standings
            )
            SELECT player_id
            FROM ordered
            WHERE rn <= v_k_lower
            ORDER BY rn
        LOOP
            UPDATE public.league_members
            SET seasonal_division_tier = v_tier
            WHERE guild_id = v_guild_id
              AND player_id = v_player_id;

            v_moves := v_moves || jsonb_build_object(
                'player_id', v_player_id,
                'from_tier', v_tier + 1,
                'to_tier', v_tier,
                'kind', 'promotion'
            );
        END LOOP;
    END LOOP;

    UPDATE public.league_seasons
    SET config_json = COALESCE(config_json, '{}'::jsonb)
        || jsonb_build_object('promo_applied', TRUE)
    WHERE id = p_season_id;

    RETURN jsonb_build_object(
        'status', 'applied',
        'season_id', p_season_id,
        'moves', v_moves
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.apply_seasonal_promotion_relegation(UUID)
    TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- REPLACE: distribute_season_prizes — per division_tier + promo/releg
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
    v_tier INT;
    v_rec RECORD;
    v_pos INT;
    v_coins INT;
    v_award TEXT;
    v_awards JSONB := '[]'::jsonb;
    v_refunds JSONB := '[]'::jsonb;
    v_refund_rec RECORD;
    v_promo JSONB;
BEGIN
    SELECT COALESCE(
        (SELECT (value_json #>> '{}')::int FROM game_config WHERE key = 'league_season_prize_pool_base'),
        3500
    )
    INTO v_pool;
    SELECT COALESCE(
        (SELECT (value_json #>> '{}')::int FROM game_config WHERE key = 'league_participation_coins'),
        150
    )
    INTO v_participation;

    SELECT l.guild_id INTO v_guild_id
    FROM league_seasons ls
    JOIN leagues l ON l.id = ls.league_id
    WHERE ls.id = p_season_id;

    FOR v_tier IN
        SELECT DISTINCT COALESCE(lp.division_tier, 1) AS division_tier
        FROM public.league_participants lp
        WHERE lp.season_id = p_season_id
          AND lp.is_active = TRUE
        ORDER BY 1
    LOOP
        v_pos := 0;

        FOR v_rec IN
            WITH standings AS (
                SELECT
                    lp.player_id,
                    p.is_ai,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id AND lf.home_score > lf.away_score THEN 3
                        WHEN lf.away_team_id = lp.player_id AND lf.away_score > lf.home_score THEN 3
                        WHEN lf.home_score = lf.away_score
                             AND lp.player_id IN (lf.home_team_id, lf.away_team_id) THEN 1
                        ELSE 0
                    END) AS pts,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id THEN lf.home_score - lf.away_score
                        WHEN lf.away_team_id = lp.player_id THEN lf.away_score - lf.home_score
                        ELSE 0
                    END) AS gd,
                    SUM(CASE
                        WHEN lf.home_team_id = lp.player_id THEN lf.home_score
                        WHEN lf.away_team_id = lp.player_id THEN lf.away_score
                        ELSE 0
                    END) AS gf
                FROM league_participants lp
                JOIN players p ON p.discord_id = lp.player_id
                LEFT JOIN league_fixtures lf ON lf.season_id = lp.season_id
                    AND lf.is_played = TRUE
                    AND lp.player_id IN (lf.home_team_id, lf.away_team_id)
                WHERE lp.season_id = p_season_id
                  AND lp.is_active = TRUE
                  AND COALESCE(lp.division_tier, 1) = v_tier
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

            INSERT INTO player_league_history (
                player_id, season_id, guild_id, finish_position, season_points, goals_for, awards_json
            )
            VALUES (
                v_rec.player_id,
                p_season_id,
                v_guild_id,
                v_pos,
                v_rec.pts,
                v_rec.gf,
                jsonb_build_array(jsonb_build_object(
                    'type', v_award,
                    'coins', v_coins,
                    'division_tier', v_tier
                ))
            )
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
                    jsonb_build_object(
                        'season_id', p_season_id,
                        'position', v_pos,
                        'award', v_award,
                        'division_tier', v_tier
                    )
                );
            END IF;

            v_awards := v_awards || jsonb_build_object(
                'player_id', v_rec.player_id,
                'position', v_pos,
                'award', v_award,
                'coins', v_coins,
                'division_tier', v_tier
            );
        END LOOP;
    END LOOP;

    -- Refund entry fees for humans who completed the season active
    FOR v_refund_rec IN
        SELECT lp.player_id, lp.entry_fee_paid
        FROM public.league_participants lp
        JOIN public.players p ON p.discord_id = lp.player_id
        WHERE lp.season_id = p_season_id
          AND lp.is_active = TRUE
          AND p.is_ai = FALSE
          AND lp.entry_fee_paid > 0
    LOOP
        PERFORM apply_club_economy(
            v_refund_rec.player_id,
            v_refund_rec.entry_fee_paid,
            0,
            'league_entry_refund',
            'league_entry_refund:' || p_season_id::text || ':' || v_refund_rec.player_id::text,
            jsonb_build_object('season_id', p_season_id, 'fee', v_refund_rec.entry_fee_paid)
        );
        v_refunds := v_refunds || jsonb_build_object(
            'player_id', v_refund_rec.player_id,
            'fee', v_refund_rec.entry_fee_paid
        );
    END LOOP;

    v_promo := public.apply_seasonal_promotion_relegation(p_season_id);

    RETURN jsonb_build_object(
        'season_id', p_season_id,
        'awards', v_awards,
        'refunds', v_refunds,
        'promo', v_promo
    );
END;
$$;

-- Match 047: service_role only for distribute_season_prizes
REVOKE EXECUTE ON FUNCTION public.distribute_season_prizes(UUID) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.distribute_season_prizes(UUID) TO service_role;

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
            ('column:public.league_seasons.pacing_mode'),
            ('column:public.league_participants.division_tier'),
            ('column:public.league_fixtures.resolved_by'),
            ('column:public.league_members.seasonal_division_tier'),
            ('table:public.league_matchday_manager_awards'),
            ('function:league_dynamics_enabled'),
            ('function:award_manager_of_the_matchday'),
            ('function:apply_seasonal_promotion_relegation'),
            ('function:distribute_season_prizes'),
            ('policy:public.league_matchday_manager_awards.league_matchday_manager_awards_select'),
            ('policy:public.league_matchday_manager_awards.league_matchday_manager_awards_insert')
    ) AS req(obj)
    WHERE NOT (
        (
            req.obj LIKE 'column:%'
            AND EXISTS (
                SELECT 1
                FROM information_schema.columns c
                WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
        OR (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
        OR (
            req.obj LIKE 'function:%'
            AND CASE split_part(req.obj, ':', 2)
                WHEN 'league_dynamics_enabled'
                    THEN to_regprocedure('public.league_dynamics_enabled()')
                WHEN 'award_manager_of_the_matchday'
                    THEN to_regprocedure('public.award_manager_of_the_matchday(uuid,integer)')
                WHEN 'apply_seasonal_promotion_relegation'
                    THEN to_regprocedure('public.apply_seasonal_promotion_relegation(uuid)')
                WHEN 'distribute_season_prizes'
                    THEN to_regprocedure('public.distribute_season_prizes(uuid)')
                ELSE NULL
            END IS NOT NULL
        )
        OR (
            req.obj LIKE 'policy:%'
            AND EXISTS (
                SELECT 1
                FROM pg_policies pol
                WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
                  AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
                  AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
            )
        )
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION '064 schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

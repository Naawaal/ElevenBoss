-- US-27: League economy hardening — entry fee sink, auto-sim tuning, calibrated game_config
-- Depends on: 032_league_mode_v2.sql

-- ---------------------------------------------------------------------------
-- league_participants.entry_fee_paid
-- ---------------------------------------------------------------------------

ALTER TABLE public.league_participants
    ADD COLUMN IF NOT EXISTS entry_fee_paid INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- game_config — calibrated defaults + US-27 keys
-- ---------------------------------------------------------------------------

INSERT INTO public.game_config (key, value_json) VALUES
    ('league_entry_fee_coins', '1500'),
    ('league_entry_fee_per_division', '250'),
    ('league_auto_sim_coin_mult', '0.5'),
    ('league_join_min_matches', '10'),
    ('league_join_min_account_days', '7')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

UPDATE public.game_config SET value_json = '3500' WHERE key = 'league_season_prize_pool_base';
UPDATE public.game_config SET value_json = '150' WHERE key = 'league_participation_coins';
UPDATE public.game_config SET value_json = '100' WHERE key = 'league_milestone_bonus_coins';
UPDATE public.game_config SET value_json = '250' WHERE key = 'match_league_win_min';
UPDATE public.game_config SET value_json = '400' WHERE key = 'match_league_win_max';

-- ---------------------------------------------------------------------------
-- charge_league_entry_fees — debit on season start (idempotent per season+player)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.charge_league_entry_fees(p_season_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_cfg JSONB;
    v_base INT;
    v_per_div INT;
    v_fee INT;
    v_rec RECORD;
    v_charged JSONB := '[]'::jsonb;
    v_skipped JSONB := '[]'::jsonb;
    v_result JSONB;
BEGIN
    SELECT config_json INTO v_cfg
    FROM public.league_seasons
    WHERE id = p_season_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Season not found: %', p_season_id;
    END IF;

    -- Season config entry_fee_coins overrides global when present (0 = free season)
    IF v_cfg ? 'entry_fee_coins' THEN
        v_base := (v_cfg ->> 'entry_fee_coins')::INT;
    ELSE
        v_base := public.get_game_config_int('league_entry_fee_coins', 1500)::INT;
    END IF;

    v_per_div := public.get_game_config_int('league_entry_fee_per_division', 250)::INT;

    FOR v_rec IN
        SELECT lp.player_id, lp.entry_fee_paid, p.division, p.is_ai, p.coins
        FROM public.league_participants lp
        JOIN public.players p ON p.discord_id = lp.player_id
        WHERE lp.season_id = p_season_id
          AND p.is_ai = FALSE
    LOOP
        IF v_rec.entry_fee_paid > 0 THEN
            v_charged := v_charged || jsonb_build_object(
                'player_id', v_rec.player_id, 'fee', v_rec.entry_fee_paid, 'replay', TRUE
            );
            CONTINUE;
        END IF;

        IF v_base <= 0 THEN
            UPDATE public.league_participants
            SET entry_fee_paid = 0
            WHERE season_id = p_season_id AND player_id = v_rec.player_id;
            v_charged := v_charged || jsonb_build_object(
                'player_id', v_rec.player_id, 'fee', 0
            );
            CONTINUE;
        END IF;

        v_fee := v_base + public.league_division_tier(v_rec.division) * v_per_div;

        IF v_rec.coins < v_fee THEN
            DELETE FROM public.league_participants
            WHERE season_id = p_season_id AND player_id = v_rec.player_id;
            v_skipped := v_skipped || jsonb_build_object(
                'player_id', v_rec.player_id,
                'reason', 'insufficient_coins',
                'fee', v_fee,
                'coins', v_rec.coins
            );
            CONTINUE;
        END IF;

        BEGIN
            v_result := public.apply_club_economy(
                v_rec.player_id,
                -v_fee,
                0,
                'league_entry',
                'league_entry:' || p_season_id::text || ':' || v_rec.player_id::text,
                jsonb_build_object('season_id', p_season_id, 'fee', v_fee)
            );

            IF COALESCE((v_result ->> 'replay')::BOOLEAN, FALSE) THEN
                SELECT entry_fee_paid INTO v_fee
                FROM public.league_participants
                WHERE season_id = p_season_id AND player_id = v_rec.player_id;
                IF v_fee IS NULL OR v_fee = 0 THEN
                    v_fee := public.get_game_config_int('league_entry_fee_coins', 1500)::INT
                        + public.league_division_tier(v_rec.division) * v_per_div;
                END IF;
            ELSE
                UPDATE public.league_participants
                SET entry_fee_paid = v_fee
                WHERE season_id = p_season_id AND player_id = v_rec.player_id;
            END IF;

            v_charged := v_charged || jsonb_build_object(
                'player_id', v_rec.player_id, 'fee', v_fee
            );
        EXCEPTION
            WHEN OTHERS THEN
                DELETE FROM public.league_participants
                WHERE season_id = p_season_id AND player_id = v_rec.player_id;
                v_skipped := v_skipped || jsonb_build_object(
                    'player_id', v_rec.player_id,
                    'reason', SQLERRM,
                    'fee', v_fee
                );
        END;
    END LOOP;

    RETURN jsonb_build_object(
        'season_id', p_season_id,
        'charged', v_charged,
        'skipped', v_skipped
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.charge_league_entry_fees(UUID) TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- distribute_season_prizes — add entry fee refund for active humans
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
    v_refunds JSONB := '[]'::jsonb;
    v_refund_rec RECORD;
BEGIN
    SELECT COALESCE((SELECT (value_json #>> '{}')::int FROM game_config WHERE key = 'league_season_prize_pool_base'), 3500)
    INTO v_pool;
    SELECT COALESCE((SELECT (value_json #>> '{}')::int FROM game_config WHERE key = 'league_participation_coins'), 150)
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

    RETURN jsonb_build_object('season_id', p_season_id, 'awards', v_awards, 'refunds', v_refunds);
END;
$$;

GRANT EXECUTE ON FUNCTION public.distribute_season_prizes(UUID) TO anon, authenticated, service_role;

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
            ('column:public.league_participants.entry_fee_paid'),
            ('function:public.charge_league_entry_fees')
    ) AS req(obj)
    WHERE NOT EXISTS (
        SELECT 1 FROM (
            SELECT 'column:' || table_schema || '.' || table_name || '.' || column_name AS obj
            FROM information_schema.columns WHERE table_schema = 'public'
            UNION ALL
            SELECT 'function:public.' || p.proname
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
        ) existing WHERE existing.obj = req.obj
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

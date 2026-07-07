-- US-30: Weekly Division Rank tier rewards + best weekly records

-- ---------------------------------------------------------------------------
-- Players: high-water weekly stats
-- ---------------------------------------------------------------------------
ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS best_weekly_pts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS best_weekly_rank INTEGER;

-- ---------------------------------------------------------------------------
-- Weekly tier claims (idempotent per ISO week + tier)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.weekly_rank_rewards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    iso_week TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('bronze', 'silver', 'gold')),
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id, iso_week, tier)
);

CREATE INDEX IF NOT EXISTS idx_weekly_rank_rewards_player_week
    ON public.weekly_rank_rewards (player_id, iso_week);

ALTER TABLE public.weekly_rank_rewards ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS weekly_rank_rewards_select ON public.weekly_rank_rewards;
CREATE POLICY weekly_rank_rewards_select ON public.weekly_rank_rewards
    FOR SELECT TO anon, authenticated, service_role USING (true);

DROP POLICY IF EXISTS weekly_rank_rewards_insert ON public.weekly_rank_rewards;
CREATE POLICY weekly_rank_rewards_insert ON public.weekly_rank_rewards
    FOR INSERT TO anon, authenticated, service_role WITH CHECK (true);

GRANT ALL ON TABLE public.weekly_rank_rewards TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- game_config tunables
-- ---------------------------------------------------------------------------
INSERT INTO public.game_config (key, value_json) VALUES
    ('weekly_tier_bronze_pts', '6'),
    ('weekly_tier_silver_pts', '12'),
    ('weekly_tier_gold_pts', '18')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- claim_weekly_rank_tier — coins via apply_club_economy
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.claim_weekly_rank_tier(
    p_player_id BIGINT,
    p_tier TEXT
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_division TEXT;
    v_pts INTEGER;
    v_iso_week TEXT;
    v_threshold INTEGER;
    v_coins INTEGER;
    v_div_tier INTEGER;
    v_existing UUID;
    v_key TEXT;
BEGIN
    IF p_tier NOT IN ('bronze', 'silver', 'gold') THEN
        RAISE EXCEPTION 'invalid tier %', p_tier;
    END IF;

    v_iso_week := to_char(NOW() AT TIME ZONE 'UTC', 'IYYY-"W"IW');

    SELECT division, league_points INTO v_division, v_pts
    FROM public.players
    WHERE discord_id = p_player_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'player not found';
    END IF;

    v_threshold := CASE p_tier
        WHEN 'bronze' THEN public.get_game_config_int('weekly_tier_bronze_pts', 6)::INTEGER
        WHEN 'silver' THEN public.get_game_config_int('weekly_tier_silver_pts', 12)::INTEGER
        ELSE public.get_game_config_int('weekly_tier_gold_pts', 18)::INTEGER
    END;

    IF v_pts < v_threshold THEN
        RETURN jsonb_build_object('ok', FALSE, 'reason', 'threshold_not_met', 'pts', v_pts, 'need', v_threshold);
    END IF;

    SELECT id INTO v_existing
    FROM public.weekly_rank_rewards
    WHERE player_id = p_player_id AND iso_week = v_iso_week AND tier = p_tier;

    IF FOUND THEN
        RETURN jsonb_build_object('ok', FALSE, 'reason', 'already_claimed', 'tier', p_tier);
    END IF;

    v_div_tier := CASE COALESCE(v_division, 'Grassroots')
        WHEN 'Grassroots' THEN 0 WHEN 'Amateur' THEN 1 WHEN 'Semi-Pro' THEN 2
        WHEN 'Professional' THEN 3 WHEN 'Elite' THEN 4 WHEN 'Legendary' THEN 5
        ELSE 0 END;

    v_coins := CASE p_tier
        WHEN 'bronze' THEN 50 + v_div_tier * 25
        WHEN 'silver' THEN 100 + v_div_tier * 50
        ELSE 200 + v_div_tier * 75
    END;

    v_key := 'weekly_tier:' || v_iso_week || ':' || p_player_id::TEXT || ':' || p_tier;

    PERFORM public.apply_club_economy(
        p_player_id, v_coins, 0, 'weekly_rank_tier', v_key,
        jsonb_build_object('tier', p_tier, 'iso_week', v_iso_week)
    );

    INSERT INTO public.weekly_rank_rewards (player_id, iso_week, tier)
    VALUES (p_player_id, v_iso_week, p_tier);

    RETURN jsonb_build_object('ok', TRUE, 'tier', p_tier, 'coins', v_coins, 'iso_week', v_iso_week);
END;
$$;

GRANT EXECUTE ON FUNCTION public.claim_weekly_rank_tier(BIGINT, TEXT) TO anon, authenticated, service_role;

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
            ('table:public.weekly_rank_rewards'),
            ('column:public.players.best_weekly_pts'),
            ('column:public.players.best_weekly_rank'),
            ('function:claim_weekly_rank_tier')
    ) AS req(obj)
    WHERE CASE
        WHEN req.obj LIKE 'table:%' THEN to_regclass(split_part(req.obj, ':', 2)) IS NULL
        WHEN req.obj LIKE 'column:%' THEN NOT EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
              AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
              AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
        )
        WHEN req.obj LIKE 'function:%' THEN to_regprocedure('public.' || split_part(req.obj, ':', 2) || '(bigint,text)') IS NULL
        ELSE FALSE
    END;

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 039 guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

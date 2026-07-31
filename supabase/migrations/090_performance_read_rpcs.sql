-- 090_performance_read_rpcs.sql
-- 050: additive page/hub read RPCs (leaderboard, market browse/sell/hub).
-- Page RPCs return at most page_size rows (no full-division payload to the bot).

CREATE OR REPLACE FUNCTION public.get_division_leaderboard_page(
    p_division text,
    p_viewer_id bigint,
    p_page int DEFAULT NULL,
    p_page_size int DEFAULT 10
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_page_size int := GREATEST(1, LEAST(COALESCE(p_page_size, 10), 25));
    v_page int;
    v_total int;
    v_viewer_rank int;
    v_viewer_pts int;
    v_viewer_gd int;
    v_n_promo int;
    v_n_releg int;
    v_rows jsonb;
    v_total_pages int;
BEGIN
    SELECT COUNT(*)::int INTO v_total
    FROM public.players
    WHERE division = p_division AND COALESCE(is_ai, false) = false;

    v_total_pages := GREATEST(1, CEIL(GREATEST(v_total, 1)::numeric / v_page_size)::int);

    SELECT league_points, goal_difference INTO v_viewer_pts, v_viewer_gd
    FROM public.players WHERE discord_id = p_viewer_id;

    SELECT 1 + COUNT(*)::int INTO v_viewer_rank
    FROM public.players p
    WHERE p.division = p_division
      AND COALESCE(p.is_ai, false) = false
      AND (
          p.league_points > COALESCE(v_viewer_pts, -1)
          OR (p.league_points = COALESCE(v_viewer_pts, -1)
              AND p.goal_difference > COALESCE(v_viewer_gd, -999999))
          OR (p.league_points = COALESCE(v_viewer_pts, -1)
              AND p.goal_difference = COALESCE(v_viewer_gd, -999999)
              AND p.discord_id < p_viewer_id)
      );

    IF p_page IS NULL THEN
        IF v_viewer_rank IS NOT NULL AND v_viewer_rank > 0 THEN
            v_page := LEAST(v_total_pages - 1, (v_viewer_rank - 1) / v_page_size);
        ELSE
            v_page := 0;
        END IF;
    ELSE
        v_page := GREATEST(0, p_page);
    END IF;
    v_page := LEAST(v_page, GREATEST(0, v_total_pages - 1));

    IF v_total <= 1 THEN
        v_n_promo := 0;
        v_n_releg := 0;
    ELSE
        v_n_promo := GREATEST(1, ROUND(v_total * 0.20)::int);
        v_n_releg := GREATEST(1, ROUND(v_total * 0.20)::int);
        IF v_n_promo + v_n_releg > v_total THEN
            v_n_promo := 1;
            v_n_releg := 1;
        END IF;
    END IF;

    SELECT COALESCE(jsonb_agg(row_to_json(t)::jsonb ORDER BY t.rank_pos), '[]'::jsonb)
    INTO v_rows
    FROM (
        SELECT * FROM (
            SELECT
                p.discord_id,
                p.club_name,
                p.league_points,
                p.goal_difference,
                ROW_NUMBER() OVER (
                    ORDER BY p.league_points DESC, p.goal_difference DESC, p.discord_id ASC
                ) AS rank_pos
            FROM public.players p
            WHERE p.division = p_division
              AND COALESCE(p.is_ai, false) = false
        ) ranked
        WHERE ranked.rank_pos > v_page * v_page_size
          AND ranked.rank_pos <= (v_page + 1) * v_page_size
    ) t;

    RETURN jsonb_build_object(
        'rows', COALESCE(v_rows, '[]'::jsonb),
        'viewer_rank', v_viewer_rank,
        'viewer_points', COALESCE(v_viewer_pts, 0),
        'viewer_gd', COALESCE(v_viewer_gd, 0),
        'total_count', v_total,
        'promotion_count', v_n_promo,
        'relegation_count', v_n_releg,
        'page', v_page,
        'page_size', v_page_size,
        'total_pages', v_total_pages
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_global_leaderboard_page(
    p_viewer_id bigint,
    p_page int DEFAULT NULL,
    p_page_size int DEFAULT 10
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_page_size int := GREATEST(1, LEAST(COALESCE(p_page_size, 10), 25));
    v_page int;
    v_total int;
    v_viewer_rank int;
    v_viewer_lp int;
    v_rows jsonb;
    v_total_pages int;
BEGIN
    SELECT COUNT(*)::int INTO v_total
    FROM public.players WHERE COALESCE(is_ai, false) = false;

    v_total_pages := GREATEST(1, CEIL(GREATEST(v_total, 1)::numeric / v_page_size)::int);

    SELECT global_lp INTO v_viewer_lp FROM public.players WHERE discord_id = p_viewer_id;

    SELECT 1 + COUNT(*)::int INTO v_viewer_rank
    FROM public.players p
    WHERE COALESCE(p.is_ai, false) = false
      AND (
          p.global_lp > COALESCE(v_viewer_lp, -1)
          OR (p.global_lp = COALESCE(v_viewer_lp, -1) AND p.discord_id < p_viewer_id)
      );

    IF p_page IS NULL THEN
        IF v_viewer_rank IS NOT NULL AND v_viewer_rank > 0 THEN
            v_page := LEAST(v_total_pages - 1, (v_viewer_rank - 1) / v_page_size);
        ELSE
            v_page := 0;
        END IF;
    ELSE
        v_page := GREATEST(0, p_page);
    END IF;
    v_page := LEAST(v_page, GREATEST(0, v_total_pages - 1));

    SELECT COALESCE(jsonb_agg(row_to_json(t)::jsonb ORDER BY t.rank_pos), '[]'::jsonb)
    INTO v_rows
    FROM (
        SELECT * FROM (
            SELECT
                p.discord_id,
                p.club_name,
                p.global_lp,
                ROW_NUMBER() OVER (ORDER BY p.global_lp DESC, p.discord_id ASC) AS rank_pos
            FROM public.players p
            WHERE COALESCE(p.is_ai, false) = false
        ) ranked
        WHERE ranked.rank_pos > v_page * v_page_size
          AND ranked.rank_pos <= (v_page + 1) * v_page_size
    ) t;

    RETURN jsonb_build_object(
        'rows', COALESCE(v_rows, '[]'::jsonb),
        'viewer_rank', v_viewer_rank,
        'viewer_lp', COALESCE(v_viewer_lp, 0),
        'total_count', v_total,
        'page', v_page,
        'page_size', v_page_size,
        'total_pages', v_total_pages
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.browse_transfer_market(
    p_position text DEFAULT 'Any',
    p_min_ovr int DEFAULT NULL,
    p_max_ovr int DEFAULT NULL,
    p_min_age int DEFAULT NULL,
    p_max_age int DEFAULT NULL,
    p_min_pot int DEFAULT NULL,
    p_max_pot int DEFAULT NULL,
    p_sort_mode text DEFAULT 'newest',
    p_limit int DEFAULT 25
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_limit int := GREATEST(1, LEAST(COALESCE(p_limit, 25), 25));
    v_sort text := COALESCE(p_sort_mode, 'newest');
    v_rows jsonb;
BEGIN
    WITH base AS (
        SELECT
            tl.id,
            tl.seller_id,
            tl.price_coins,
            tl.created_at,
            tl.expires_at,
            tl.card_id,
            pc.name,
            pc.position,
            pc.overall,
            pc.potential,
            pc.rarity,
            pc.date_of_birth,
            pc.owner_id,
            COALESCE(
                EXTRACT(YEAR FROM age(CURRENT_DATE, pc.date_of_birth::date))::int,
                pc.age,
                25
            ) AS card_age
        FROM public.transfer_listings tl
        JOIN public.player_cards pc ON pc.id = tl.card_id
        WHERE tl.status = 'active'
          AND tl.expires_at > NOW()
          AND (p_position IS NULL OR p_position = 'Any' OR pc.position = p_position)
          AND (p_min_ovr IS NULL OR pc.overall >= p_min_ovr)
          AND (p_max_ovr IS NULL OR pc.overall <= p_max_ovr)
          AND (p_min_pot IS NULL OR pc.potential >= p_min_pot)
          AND (p_max_pot IS NULL OR pc.potential <= p_max_pot)
          AND (
              p_min_age IS NULL OR COALESCE(
                  EXTRACT(YEAR FROM age(CURRENT_DATE, pc.date_of_birth::date))::int,
                  pc.age, 25
              ) >= p_min_age
          )
          AND (
              p_max_age IS NULL OR COALESCE(
                  EXTRACT(YEAR FROM age(CURRENT_DATE, pc.date_of_birth::date))::int,
                  pc.age, 25
              ) <= p_max_age
          )
    ),
    ordered AS (
        SELECT * FROM base
        ORDER BY
            CASE WHEN v_sort = 'lowest_price' THEN price_coins END ASC NULLS LAST,
            CASE WHEN v_sort = 'highest_price' THEN price_coins END DESC NULLS LAST,
            CASE WHEN v_sort = 'highest_ovr' THEN overall END DESC NULLS LAST,
            CASE WHEN v_sort = 'highest_potential' THEN potential END DESC NULLS LAST,
            CASE WHEN v_sort = 'ending_soon' THEN expires_at END ASC NULLS LAST,
            CASE WHEN v_sort = 'newest' THEN created_at END DESC NULLS LAST,
            created_at DESC,
            id DESC
        LIMIT v_limit
    )
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id', o.id,
        'seller_id', o.seller_id,
        'price_coins', o.price_coins,
        'created_at', o.created_at,
        'expires_at', o.expires_at,
        '_age', o.card_age,
        'player_cards', jsonb_build_object(
            'id', o.card_id,
            'name', o.name,
            'position', o.position,
            'overall', o.overall,
            'potential', o.potential,
            'rarity', o.rarity,
            'date_of_birth', o.date_of_birth,
            'owner_id', o.owner_id
        )
    )), '[]'::jsonb)
    INTO v_rows
    FROM ordered o;

    RETURN jsonb_build_object('listings', COALESCE(v_rows, '[]'::jsonb), 'sort_mode', v_sort);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_market_sell_eligible_cards(p_owner_id bigint)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_rows jsonb;
BEGIN
    SELECT COALESCE(jsonb_agg(row_to_json(t)::jsonb ORDER BY t.overall DESC), '[]'::jsonb)
    INTO v_rows
    FROM (
        SELECT
            pc.id,
            pc.name,
            pc.position,
            pc.overall,
            pc.potential,
            pc.rarity,
            pc.date_of_birth,
            pc.injury_tier,
            pc.in_hospital
        FROM public.player_cards pc
        WHERE pc.owner_id = p_owner_id
          AND COALESCE(pc.is_retired, false) = false
          AND COALESCE(pc.in_academy, false) = false
          AND NOT EXISTS (
              SELECT 1 FROM public.squad_assignments sa
              WHERE sa.discord_id = p_owner_id AND sa.player_card_id = pc.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM public.active_evolutions ae
              WHERE ae.owner_id = p_owner_id AND ae.status = 'active' AND ae.card_id = pc.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM public.active_training at
              WHERE at.club_id = p_owner_id AND at.card_id = pc.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM public.transfer_listings tl
              WHERE tl.seller_id = p_owner_id AND tl.status = 'active' AND tl.card_id = pc.id
          )
        ORDER BY pc.overall DESC
    ) t;

    RETURN jsonb_build_object('cards', COALESCE(v_rows, '[]'::jsonb));
END;
$$;

CREATE OR REPLACE FUNCTION public.get_marketplace_hub_state(p_owner_id bigint)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_player public.players%ROWTYPE;
    v_enabled boolean := false;
    v_count int := 0;
    v_cap int := 5;
    v_cap_raw text;
BEGIN
    SELECT * INTO v_player FROM public.players WHERE discord_id = p_owner_id;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'player_not_found');
    END IF;

    BEGIN
        v_enabled := public.p2p_transfer_market_enabled();
    EXCEPTION WHEN OTHERS THEN
        v_enabled := false;
    END;

    IF v_enabled THEN
        SELECT COUNT(*)::int INTO v_count
        FROM public.transfer_listings
        WHERE seller_id = p_owner_id AND status = 'active';
        BEGIN
            SELECT value_json #>> '{}' INTO v_cap_raw
            FROM public.game_config WHERE key = 'transfer_listing_slot_cap';
            IF v_cap_raw IS NOT NULL AND v_cap_raw ~ '^[0-9]+$' THEN
                v_cap := v_cap_raw::int;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            v_cap := 5;
        END;
    END IF;

    RETURN jsonb_build_object(
        'ok', true,
        'manager_name', v_player.manager_name,
        'coins', COALESCE(v_player.coins, 0),
        'tokens', COALESCE(v_player.tokens, 0),
        'transfer_enabled', v_enabled,
        'active_listing_count', v_count,
        'listing_cap', v_cap
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_division_leaderboard_page(text, bigint, int, int)
    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_global_leaderboard_page(bigint, int, int)
    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.browse_transfer_market(text, int, int, int, int, int, int, text, int)
    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_market_sell_eligible_cards(bigint)
    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_marketplace_hub_state(bigint)
    TO anon, authenticated, service_role;

DO $$
BEGIN
    IF to_regprocedure('public.get_division_leaderboard_page(text, bigint, integer, integer)') IS NULL THEN
        RAISE EXCEPTION '090 guard failed: get_division_leaderboard_page';
    END IF;
    IF to_regprocedure('public.get_global_leaderboard_page(bigint, integer, integer)') IS NULL THEN
        RAISE EXCEPTION '090 guard failed: get_global_leaderboard_page';
    END IF;
    IF to_regprocedure(
        'public.browse_transfer_market(text, integer, integer, integer, integer, integer, integer, text, integer)'
    ) IS NULL THEN
        RAISE EXCEPTION '090 guard failed: browse_transfer_market';
    END IF;
    IF to_regprocedure('public.get_market_sell_eligible_cards(bigint)') IS NULL THEN
        RAISE EXCEPTION '090 guard failed: get_market_sell_eligible_cards';
    END IF;
    IF to_regprocedure('public.get_marketplace_hub_state(bigint)') IS NULL THEN
        RAISE EXCEPTION '090 guard failed: get_marketplace_hub_state';
    END IF;
END $$;

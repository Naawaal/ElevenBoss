-- 096_academy_scout_fog_floor.sql
-- FR-010: keep scout range fog floor for all assessment tiers (not Deep-only).
-- Forward fix after 095; do not edit 095 in place on remote.

BEGIN;

CREATE OR REPLACE FUNCTION public.academy_narrow_visible_range(
    p_lo INTEGER,
    p_hi INTEGER,
    p_potential INTEGER,
    p_rarity TEXT,
    p_tier TEXT,
    OUT o_lo INTEGER,
    OUT o_hi INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_cap INTEGER;
    v_pot INTEGER;
    v_trim INTEGER;
    v_tier TEXT := lower(trim(p_tier));
    v_min_w INTEGER;
    v_cur_lo INTEGER;
    v_cur_hi INTEGER;
BEGIN
    v_cap := public.rarity_potential_cap(p_rarity);
    v_pot := GREATEST(1, LEAST(COALESCE(p_potential, 1), v_cap));
    v_cur_lo := GREATEST(1, LEAST(COALESCE(p_lo, v_pot), v_pot, v_cap));
    v_cur_hi := LEAST(v_cap, GREATEST(COALESCE(p_hi, v_pot), v_pot));
    IF v_tier = 'quick' THEN
        v_trim := public.get_game_config_int('scout_narrow_quick', 2)::INTEGER;
    ELSIF v_tier = 'standard' THEN
        v_trim := public.get_game_config_int('scout_narrow_standard', 3)::INTEGER;
    ELSIF v_tier = 'deep' THEN
        v_trim := public.get_game_config_int('scout_narrow_deep', 4)::INTEGER;
    ELSE
        RAISE EXCEPTION 'Invalid assessment tier';
    END IF;
    o_lo := GREATEST(v_cur_lo, LEAST(v_pot, v_cur_lo + v_trim));
    o_hi := LEAST(v_cur_hi, GREATEST(v_pot, v_cur_hi - v_trim));
    o_lo := LEAST(o_lo, v_pot);
    o_hi := GREATEST(o_hi, v_pot);
    v_min_w := public.get_game_config_int('scout_deep_min_range', 2)::INTEGER;
    WHILE (o_hi - o_lo + 1) < v_min_w AND (o_lo > v_cur_lo OR o_hi < v_cur_hi) LOOP
        IF o_lo > v_cur_lo AND (o_hi - o_lo + 1) < v_min_w THEN
            o_lo := o_lo - 1;
        END IF;
        IF o_hi < v_cur_hi AND (o_hi - o_lo + 1) < v_min_w THEN
            o_hi := o_hi + 1;
        END IF;
    END LOOP;
    o_lo := LEAST(o_lo, v_pot);
    o_hi := GREATEST(o_hi, v_pot);
END;
$$;

GRANT ALL PRIVILEGES ON FUNCTION public.academy_narrow_visible_range(INTEGER, INTEGER, INTEGER, TEXT, TEXT)
    TO anon, authenticated, service_role;

COMMIT;

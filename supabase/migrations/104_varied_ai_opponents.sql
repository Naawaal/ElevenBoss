-- supabase/migrations/104_varied_ai_opponents.sql
-- Fix: AI backfill always showed the same club name and identical players.
-- Replace build_calibrated_pvp_ai_snapshot with a version that:
--   1. Picks a random fictional club name from a 20-entry pool.
--   2. Varies formation across 5 common shapes.
--   3. Adds ±3 per-player stat noise so no two AIs feel identical.

DROP FUNCTION IF EXISTS public.build_calibrated_pvp_ai_snapshot(NUMERIC, TEXT);

CREATE OR REPLACE FUNCTION public.build_calibrated_pvp_ai_snapshot(
    p_target_ovr NUMERIC,
    p_division    TEXT DEFAULT 'Professional'
) RETURNS JSONB
LANGUAGE plpgsql
-- ponytail: VOLATILE (not STABLE) because random() is called inside
AS $$
DECLARE
    v_base_ovr INTEGER := LEAST(99, GREATEST(40, ROUND(p_target_ovr)::INTEGER));

    -- 20 fictional club names – seeded once per call so results feel human
    v_club_names TEXT[] := ARRAY[
        'Iron Phalanx FC',    'Azure Storm United',  'Crimson Vanguard',
        'Shadow Wolves SC',   'Titan Athletic',       'Golden Eagle CF',
        'Obsidian City FC',   'Silver Fox United',    'Thunderbolt SC',
        'Hollow Crown FC',    'Midnight Rovers',      'Cobalt Strike FC',
        'Desert Storm SC',    'Northern Legends FC',  'Steel Curtain United',
        'Phantom Rangers',    'Ember Knights FC',     'Apex Predators SC',
        'Irongate Athletic',  'Vortex FC'
    ];

    -- 5 common formations with matching positional maps
    v_formations TEXT[] := ARRAY['4-3-3', '4-4-2', '4-2-3-1', '3-5-2', '5-3-2'];
    v_pos_maps   TEXT[][] := ARRAY[
        -- 4-3-3
        ARRAY['GK','CB','CB','LB','RB','CM','CM','CM','LW','RW','ST'],
        -- 4-4-2
        ARRAY['GK','CB','CB','LB','RB','LM','CM','CM','RM','ST','ST'],
        -- 4-2-3-1
        ARRAY['GK','CB','CB','LB','RB','CDM','CDM','CAM','LW','RW','ST'],
        -- 3-5-2
        ARRAY['GK','CB','CB','CB','LWB','CM','CM','CM','RWB','ST','ST'],
        -- 5-3-2
        ARRAY['GK','CB','CB','CB','LWB','RWB','CM','CM','CM','ST','ST']
    ];

    v_pick      INTEGER;
    v_club_name TEXT;
    v_formation TEXT;
    v_positions TEXT[];
    v_squad     JSONB;
    v_pos       TEXT;
    v_noise     INTEGER;
    v_ovr       INTEGER;
    i           INTEGER;
BEGIN
    -- Pick random club and formation (1-indexed)
    v_pick      := 1 + (floor(random() * array_length(v_club_names, 1)))::INTEGER;
    v_club_name := v_club_names[v_pick];

    v_pick      := 1 + (floor(random() * array_length(v_formations, 1)))::INTEGER;
    v_formation := v_formations[v_pick];

    v_squad := '[]'::jsonb;
    FOR i IN 1..11 LOOP
        v_pos   := v_pos_maps[v_pick][i];
        -- per-player noise in [-3, +3], clamped to [40, 99]
        v_noise := (floor(random() * 7) - 3)::INTEGER;
        v_ovr   := LEAST(99, GREATEST(40, v_base_ovr + v_noise));

        v_squad := v_squad || jsonb_build_object(
            'name',       'AI ' || v_pos || ' ' || i,
            'position',   v_pos,
            'overall',    v_ovr,
            'pac',        LEAST(99, GREATEST(40, v_ovr + (floor(random() * 5) - 2)::INTEGER)),
            'sho',        LEAST(99, GREATEST(40, v_ovr + (floor(random() * 5) - 2)::INTEGER)),
            'pas',        LEAST(99, GREATEST(40, v_ovr + (floor(random() * 5) - 2)::INTEGER)),
            'dri',        LEAST(99, GREATEST(40, v_ovr + (floor(random() * 5) - 2)::INTEGER)),
            'def_stat',   LEAST(99, GREATEST(40, v_ovr + (floor(random() * 5) - 2)::INTEGER)),
            'phy',        LEAST(99, GREATEST(40, v_ovr + (floor(random() * 5) - 2)::INTEGER)),
            'morale',     80 + (floor(random() * 16))::INTEGER,
            'playstyles', '[]'::jsonb
        );
    END LOOP;

    RETURN jsonb_build_object(
        'owner_id',  NULL,
        'club_name', v_club_name,
        'formation', v_formation,
        'tactics',   jsonb_build_object(
            'stance',         (ARRAY['balanced','attacking','defensive'])[1 + (floor(random() * 3))::INTEGER],
            'intensity_tier', 1 + (floor(random() * 3))::INTEGER
        ),
        'xi_rating',           ROUND(p_target_ovr, 2),
        'squad',               v_squad,
        'card_ids',            '[]'::jsonb,
        'card_meta',           '[]'::jsonb,
        'finalization_policy', jsonb_build_object(
            'economy_enabled',  true,
            'xp_enabled',       true,
            'fitness_enabled',  true,
            'rivalry_enabled',  false
        )
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.build_calibrated_pvp_ai_snapshot(NUMERIC, TEXT)
    TO anon, authenticated, service_role;

-- ── Schema guard ──────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF to_regprocedure('public.build_calibrated_pvp_ai_snapshot(numeric,text)') IS NULL THEN
        RAISE EXCEPTION 'Migration 104: build_calibrated_pvp_ai_snapshot not found after replacement';
    END IF;
END $$;

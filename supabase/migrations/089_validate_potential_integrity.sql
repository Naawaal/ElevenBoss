-- 089_validate_potential_integrity.sql
-- US-42.9 — VALIDATE rarity POT CHECKs after historical repair (049).
-- Apply ONLY when anomaly count = 0.

CREATE OR REPLACE FUNCTION public.count_potential_integrity_anomalies()
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(*)::INTEGER
    FROM public.player_cards
    WHERE public.rarity_potential_cap(rarity) IS NULL
       OR potential > public.rarity_potential_cap(rarity)
       OR (
            base_potential IS NOT NULL
            AND base_potential > public.rarity_potential_cap(rarity)
       )
       OR overall > potential;
$$;

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT public.count_potential_integrity_anomalies() INTO v_count;
    IF v_count <> 0 THEN
        RAISE EXCEPTION
            '089 refused: % potential integrity anomalies remain — repair before VALIDATE',
            v_count;
    END IF;

    ALTER TABLE public.player_cards
        VALIDATE CONSTRAINT player_cards_potential_rarity_cap_chk;
    ALTER TABLE public.player_cards
        VALIDATE CONSTRAINT player_cards_base_potential_rarity_cap_chk;
    ALTER TABLE public.player_cards
        VALIDATE CONSTRAINT player_cards_overall_potential_chk;
END $$;

-- Rollout flag is temporary; constraints are permanent. Do not re-open caps via config.
COMMENT ON FUNCTION public.rarity_potential_cap(TEXT) IS
    'Absolute rarity POT ceiling (049). game_config.potential_rarity_caps_enabled is rollout-only and must not disable CHECKs.';

DO $$
BEGIN
    IF to_regprocedure('public.count_potential_integrity_anomalies()') IS NULL THEN
        RAISE EXCEPTION '089 missing count_potential_integrity_anomalies';
    END IF;
END $$;

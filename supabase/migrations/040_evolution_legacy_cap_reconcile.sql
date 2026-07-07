-- Reconcile pre-023 evolution rows: cap active tracks at 3 per club, normalize legacy columns.

-- 1. Backfill owner_id on any orphaned rows
UPDATE public.active_evolutions e
SET owner_id = pc.owner_id
FROM public.player_cards pc
WHERE pc.id = e.card_id
  AND e.owner_id IS NULL;

-- 2. Normalize legacy progress columns so match ticks and hub display agree
UPDATE public.active_evolutions
SET
    target_metric = 'matches',
    target_goal = COALESCE(NULLIF(target_goal, 0), matches_required, 3),
    matches_required = COALESCE(matches_required, NULLIF(target_goal, 0), 3),
    current_progress = COALESCE(current_progress, matches_played, 0),
    matches_played = COALESCE(matches_played, current_progress, 0),
    started_at = COALESCE(started_at, created_at, NOW())
WHERE status = 'active';

-- 3. Cancel overflow beyond 3 active evolutions per club (keep best progress, then newest)
WITH ranked AS (
    SELECT
        e.id,
        ROW_NUMBER() OVER (
            PARTITION BY e.owner_id
            ORDER BY
                COALESCE(e.matches_played, e.current_progress, 0) DESC,
                COALESCE(e.started_at, e.created_at) DESC,
                e.id DESC
        ) AS rn
    FROM public.active_evolutions e
    WHERE e.status = 'active'
      AND e.owner_id IS NOT NULL
)
UPDATE public.active_evolutions e
SET
    status = 'cancelled',
    cancelled_at = NOW(),
    matches_played = 0,
    current_progress = 0
FROM ranked r
WHERE e.id = r.id
  AND r.rn > 3;

-- ---------------------------------------------------------------------------
-- Schema guard
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_overflow INTEGER;
BEGIN
    SELECT COUNT(*)::INTEGER
    INTO v_overflow
    FROM (
        SELECT owner_id
        FROM public.active_evolutions
        WHERE status = 'active' AND owner_id IS NOT NULL
        GROUP BY owner_id
        HAVING COUNT(*) > 3
    ) t;

    IF v_overflow > 0 THEN
        RAISE EXCEPTION 'Migration 040 guard failed — % clubs still have >3 active evolutions', v_overflow;
    END IF;

    RAISE NOTICE 'Migration 040 evolution legacy cap reconcile OK';
END $$;

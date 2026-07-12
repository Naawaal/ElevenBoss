-- 059: Crash-safe post-match fatigue gate (bench rest / starter drain)
-- Separates fitness idempotency from xp_applied_at so a failed fitness call
-- can still run on retry without double-applying XP.

ALTER TABLE public.match_history
    ADD COLUMN IF NOT EXISTS fatigue_applied_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'match_history'
          AND column_name = 'fatigue_applied_at'
    ) THEN
        RAISE EXCEPTION 'Migration 059 guard failed — match_history.fatigue_applied_at missing';
    END IF;
END;
$$;

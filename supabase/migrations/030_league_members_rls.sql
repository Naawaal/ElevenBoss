-- US-22: league_members had RLS enabled with zero policies (INSERT 42501 via anon key).
-- Bot uses SUPABASE_KEY (anon) for all Data API calls; add policies matching app-layer checks.

ALTER TABLE public.league_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS league_members_select ON public.league_members;
DROP POLICY IF EXISTS league_members_insert ON public.league_members;

CREATE POLICY league_members_select ON public.league_members
    FOR SELECT
    TO anon, authenticated, service_role
    USING (true);

CREATE POLICY league_members_insert ON public.league_members
    FOR INSERT
    TO anon, authenticated, service_role
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.players p
            WHERE p.discord_id = player_id
              AND p.is_ai = FALSE
        )
    );

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
    SELECT array_agg(req.obj ORDER BY req.obj)
    INTO v_missing
    FROM (
        VALUES
            ('policy:public.league_members.league_members_select'),
            ('policy:public.league_members.league_members_insert')
    ) AS req(obj)
    WHERE NOT EXISTS (
        SELECT 1
        FROM pg_policies pol
        WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
          AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
          AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
    );

    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'Schema guard failed — missing: %', array_to_string(v_missing, ', ');
    END IF;
END $$;

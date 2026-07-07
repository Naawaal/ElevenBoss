-- US-22: Codify RLS + policies standard for bot-exposed tables.
-- If RLS is enabled on a bot-required table, it MUST have at least one policy
-- (league_members 42501 was RLS on + zero policies). See AGENTS.md §8.

DO $$
DECLARE
    v_bad TEXT[];
BEGIN
    SELECT array_agg(c.relname ORDER BY c.relname)
    INTO v_bad
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relrowsecurity = TRUE
      AND c.relname IN (
          'players',
          'player_cards',
          'active_evolutions',
          'active_training',
          'economy_ledger',
          'league_members',
          'match_locks',
          'match_runs',
          'pending_level_rewards',
          'fusion_daily_log',
          'player_drill_daily_log',
          'game_config',
          'agent_sale_daily_log',
          'energy_refill_daily_log',
          'guild_config',
          'leagues',
          'league_seasons',
          'league_participants',
          'league_fixtures',
          'match_logs',
          'player_season_stats',
          'match_history',
          'friendly_match_logs'
      )
      AND NOT EXISTS (
          SELECT 1
          FROM pg_policies p
          WHERE p.schemaname = 'public'
            AND p.tablename = c.relname
      );

    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'RLS guard failed — tables with RLS enabled but no policies: %', array_to_string(v_bad, ', ');
    END IF;
END $$;

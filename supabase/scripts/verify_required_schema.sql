-- Run after migrations: psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql
-- Exits non-zero (via RAISE) if required ElevenBoss objects are missing.

DO $$
DECLARE
    v_missing TEXT[];
BEGIN
  SELECT array_agg(req.obj ORDER BY req.obj)
  INTO v_missing
  FROM (
    VALUES
      ('table:public.players'),
      ('table:public.player_cards'),
      ('table:public.active_evolutions'),
      ('table:public.active_training'),
      ('table:public.economy_ledger'),
      ('table:public.league_members'),
      ('table:public.league_season_awards'),
      ('table:public.player_league_history'),
      ('table:public.league_matchday_milestones'),
      ('table:public.match_locks'),
      ('table:public.match_runs'),
      ('column:public.league_seasons.config_json'),
      ('column:public.league_seasons.announcement_message_id'),
      ('column:public.league_seasons.journal_thread_id'),
      ('column:public.league_seasons.matchday_thread_id'),
      ('column:public.league_seasons.thread_format'),
      ('column:public.player_cards.recent_match_ratings'),
      ('table:public.league_matchday_reminders'),
      ('column:public.league_participants.entry_fee_paid'),
      ('column:public.players.training_energy'),
      ('column:public.players.daily_drill_count'),
      ('column:public.players.daily_drill_reset_at'),
      ('column:public.players.last_evolution_started_at'),
      ('column:public.player_cards.skill_points_earned'),
      ('column:public.player_cards.skill_points_spent'),
      ('column:public.player_cards.last_level_up_at'),
      ('table:public.pending_level_rewards'),
      ('table:public.fusion_daily_log'),
      ('table:public.player_drill_daily_log'),
      ('table:public.game_config'),
      ('table:public.agent_sale_daily_log'),
      ('table:public.energy_refill_daily_log'),
      ('column:public.player_cards.daily_alloc_count'),
      ('column:public.player_cards.alloc_reset_date'),
      ('column:public.players.action_energy'),
      ('column:public.players.last_daily_login'),
      ('column:public.match_history.run_id'),
      ('column:public.match_history.xp_applied_at'),
      ('column:public.economy_ledger.idempotency_key'),
      ('function:apply_card_xp'),
      ('function:apply_club_economy'),
      ('function:compute_card_ovr'),
      ('function:peek_card_ovr'),
      ('function:evolution_stat_reward_steps'),
      ('function:claim_evolution_reward'),
      ('function:start_player_evolution'),
      ('function:claim_pending_level_rewards'),
      ('function:level_from_xp'),
      ('function:count_unclaimed_level_rewards'),
      ('function:daily_match_xp_used'),
      ('function:distribute_season_prizes'),
      ('function:charge_league_entry_fees'),
      ('function:process_match_result'),
      ('function:claim_daily_pack'),
      ('policy:public.league_members.league_members_select'),
      ('policy:public.league_matchday_reminders.league_matchday_reminders_select'),
      ('policy:public.league_matchday_reminders.league_matchday_reminders_insert'),
      ('policy:public.league_members.league_members_insert')
  ) AS req(obj)
  WHERE NOT (
    (req.obj LIKE 'table:%' AND to_regclass(split_part(req.obj, ':', 2)) IS NOT NULL)
    OR (
      req.obj LIKE 'column:%'
      AND EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = split_part(split_part(req.obj, ':', 2), '.', 1)
          AND c.table_name = split_part(split_part(req.obj, ':', 2), '.', 2)
          AND c.column_name = split_part(split_part(req.obj, ':', 2), '.', 3)
      )
    )
    OR (
      req.obj LIKE 'policy:%'
      AND EXISTS (
        SELECT 1
        FROM pg_policies pol
        WHERE pol.schemaname = split_part(split_part(req.obj, ':', 2), '.', 1)
          AND pol.tablename = split_part(split_part(req.obj, ':', 2), '.', 2)
          AND pol.policyname = split_part(split_part(req.obj, ':', 2), '.', 3)
      )
    )
    OR (
      req.obj LIKE 'function:%'
      AND CASE split_part(req.obj, ':', 2)
        WHEN 'process_stat_drill' THEN to_regprocedure('public.process_stat_drill(bigint,uuid,text)')
        WHEN 'sync_training_energy' THEN to_regprocedure('public.sync_training_energy(bigint)')
        WHEN 'get_evolution_hub_status' THEN to_regprocedure('public.get_evolution_hub_status(bigint)')
        WHEN 'apply_card_xp' THEN to_regprocedure('public.apply_card_xp(uuid,integer,text)')
        WHEN 'apply_club_economy' THEN to_regprocedure('public.apply_club_economy(bigint,bigint,integer,text,text,jsonb)')
        WHEN 'compute_card_ovr' THEN to_regprocedure('public.compute_card_ovr(text,integer,integer,integer,integer,integer,integer,integer,uuid)')
        WHEN 'peek_card_ovr' THEN to_regprocedure('public.peek_card_ovr(uuid,text,integer)')
        WHEN 'evolution_stat_reward_steps' THEN to_regprocedure('public.evolution_stat_reward_steps(uuid,text,integer)')
        WHEN 'claim_evolution_reward' THEN to_regprocedure('public.claim_evolution_reward(bigint,uuid)')
        WHEN 'start_player_evolution' THEN to_regprocedure('public.start_player_evolution(bigint,uuid,text)')
        WHEN 'claim_pending_level_rewards' THEN to_regprocedure('public.claim_pending_level_rewards(bigint)')
        WHEN 'level_from_xp' THEN to_regprocedure('public.level_from_xp(integer)')
        WHEN 'count_unclaimed_level_rewards' THEN to_regprocedure('public.count_unclaimed_level_rewards(bigint)')
        WHEN 'daily_match_xp_used' THEN to_regprocedure('public.daily_match_xp_used(uuid)')
        WHEN 'sync_action_energy' THEN to_regprocedure('public.sync_action_energy(bigint)')
        WHEN 'claim_daily_login' THEN to_regprocedure('public.claim_daily_login(bigint)')
        WHEN 'purchase_energy_refill' THEN to_regprocedure('public.purchase_energy_refill(bigint)')
        WHEN 'get_game_config' THEN to_regprocedure('public.get_game_config(text)')
        WHEN 'distribute_season_prizes' THEN to_regprocedure('public.distribute_season_prizes(uuid)')
        WHEN 'charge_league_entry_fees' THEN to_regprocedure('public.charge_league_entry_fees(uuid)')
        WHEN 'process_match_result' THEN to_regprocedure('public.process_match_result(text,uuid[],integer,numeric[],integer[])')
        WHEN 'claim_daily_pack' THEN to_regprocedure('public.claim_daily_pack(bigint,jsonb)')
        WHEN 'formation_slot_role' THEN to_regprocedure('public.formation_slot_role(text,integer)')
        ELSE NULL
      END IS NOT NULL
    )
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema verify failed — missing: %', array_to_string(v_missing, ', ');
  END IF;

  -- RLS-on-without-policies guard (same as migration 031)
  PERFORM 1
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relkind = 'r'
    AND c.relrowsecurity = TRUE
    AND c.relname IN (
        'players', 'player_cards', 'active_evolutions', 'active_training',
        'economy_ledger', 'league_members', 'match_locks', 'match_runs',
        'league_fixtures', 'league_seasons', 'league_participants', 'match_logs',
        'player_season_stats', 'league_season_awards', 'player_league_history',
        'league_matchday_milestones',
        'pending_level_rewards', 'fusion_daily_log', 'player_drill_daily_log',
        'game_config', 'agent_sale_daily_log', 'energy_refill_daily_log'
    )
    AND NOT EXISTS (
        SELECT 1 FROM pg_policies p
        WHERE p.schemaname = 'public' AND p.tablename = c.relname
    );
  IF FOUND THEN
    RAISE EXCEPTION 'Schema verify failed — bot-required table has RLS enabled with zero policies';
  END IF;

  RAISE NOTICE 'Schema verify OK';
END $$;

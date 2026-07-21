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
      ('column:public.league_seasons.pacing_mode'),
      ('column:public.league_participants.division_tier'),
      ('column:public.league_fixtures.resolved_by'),
      ('column:public.league_members.seasonal_division_tier'),
      ('column:public.league_members.registered_at'),
      ('table:public.league_matchday_manager_awards'),
      ('table:public.league_registrations'),
      ('table:public.league_divisions'),
      ('table:public.league_matchdays'),
      ('table:public.league_final_standings'),
      ('table:public.league_transition_journal'),
      ('table:public.league_operation_runs'),
      ('table:public.league_outbox'),
      ('column:public.guild_config.league_automation_enabled'),
      ('column:public.guild_config.next_auto_registration_at'),
      ('column:public.guild_config.automation_last_error'),
      ('column:public.guild_config.league_timezone'),
      ('column:public.guild_config.league_resolution_hour_local'),
      ('column:public.guild_config.league_lifecycle_v1_enabled'),
      ('column:public.league_seasons.ruleset_version'),
      ('column:public.league_seasons.engine_version'),
      ('column:public.league_seasons.timezone'),
      ('column:public.league_seasons.resolution_hour_local'),
      ('column:public.league_seasons.phase_deadlines'),
      ('column:public.league_fixtures.result_type'),
      ('column:public.league_fixtures.matchday_id'),
      ('column:public.league_participants.division_id'),
      ('column:public.league_members.status'),
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
      ('table:public.transfer_listings'),
      ('table:public.transfer_sales_log'),
      ('table:public.payroll_runs'),
      ('column:public.players.payroll_debt'),
      ('column:public.players.payroll_strikes'),
      ('column:public.players.last_payroll_at'),
      ('column:public.players.last_payroll_week'),
      ('column:public.player_cards.daily_alloc_count'),
      ('column:public.player_cards.alloc_reset_date'),
      ('column:public.players.action_energy'),
      ('column:public.players.best_weekly_pts'),
      ('column:public.players.best_weekly_rank'),
      ('table:public.weekly_rank_rewards'),
      ('column:public.players.last_daily_login'),
      ('column:public.players.last_consumed_topgg_vote_at'),
      ('column:public.match_history.run_id'),
      ('column:public.match_history.xp_applied_at'),
      ('column:public.match_history.fatigue_applied_at'),
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
      ('function:league_dynamics_enabled'),
      ('function:league_automation_enabled'),
      ('function:league_lifecycle_v1_enabled'),
      ('function:award_manager_of_the_matchday'),
      ('function:apply_seasonal_promotion_relegation'),
      ('function:charge_league_entry_fees'),
      ('function:claim_weekly_rank_tier'),
      ('function:process_match_result'),
      ('function:acquire_match_lock'),
      ('function:release_match_lock'),
      ('function:increment_match_career_stats'),
      ('function:increment_league_career_stats'),
      ('function:upsert_matchday_milestone_points'),
      ('function:train_with_fodder'),
      ('function:process_agent_sale'),
      ('function:allocate_skill_point'),
      ('function:renew_contract'),
      ('function:cancel_player_evolution'),
      ('function:process_stat_drill'),
      ('column:public.player_cards.date_of_birth'),
      ('column:public.player_cards.is_retired'),
      ('function:card_age_from_dob'),
      ('function:card_xp_age_multiplier'),
      ('function:retire_player_card'),
      ('column:public.players.youth_academy_level'),
      ('column:public.players.training_ground_level'),
      ('function:training_ground_xp_bonus'),
      ('function:upgrade_club_facility'),
      ('column:public.player_cards.fatigue'),
      ('column:public.player_cards.injury_tier'),
      ('column:public.player_cards.in_hospital'),
      ('column:public.players.hospital_level'),
      ('column:public.players.squad_invalid'),
      ('table:public.hospital_patients'),
      ('function:apply_match_fatigue'),
      ('function:process_post_match_injuries'),
      ('function:process_daily_recovery'),
      ('function:admit_to_hospital'),
      ('function:discharge_from_hospital'),
      ('policy:public.hospital_patients.hospital_patients_select'),
      ('function:insert_scouting_pool_player'),
      ('function:purchase_scouting_player'),
      ('table:public.scouting_pool_players'),
      ('column:public.player_cards.role'),
      ('column:public.scouting_pool_players.role'),
      ('function:p2p_transfer_market_enabled'),
      ('function:card_is_on_transfer_list'),
      ('function:assert_card_not_on_transfer_list'),
      ('function:create_transfer_listing'),
      ('function:cancel_transfer_listing'),
      ('function:purchase_transfer_listing'),
      ('function:expire_stale_transfer_listings'),
      ('function:wages_payroll_enabled'),
      ('function:payroll_utc_week_key'),
      ('function:card_weekly_wage_coins'),
      ('function:club_xi_weekly_wage_bill'),
      ('function:card_contract_blocks_xi'),
      ('function:assert_club_payroll_market_ok'),
      ('function:process_club_weekly_payroll'),
      ('function:process_weekly_payroll'),
      ('policy:public.transfer_listings.transfer_listings_select'),
      ('policy:public.transfer_sales_log.transfer_sales_log_select'),
      ('policy:public.payroll_runs.payroll_runs_select'),
      ('policy:public.payroll_runs.payroll_runs_insert'),
      ('policy:public.payroll_runs.payroll_runs_update'),
      ('function:process_youth_intake'),
      ('table:public.youth_intake_log'),
      ('table:public.mentor_transfer_log'),
      ('function:transfer_mentor_xp'),
      ('function:process_recovery_session'),
      ('function:process_recovery_batch'),
      ('table:public.support_legendary_rewards'),
      ('function:prepare_support_legendary_reward'),
      ('function:claim_support_legendary_reward'),
      ('function:support_legendary_reward_pending'),
      ('policy:public.support_legendary_rewards.support_legendary_rewards_select'),
      ('policy:public.support_legendary_rewards.support_legendary_rewards_update'),
      ('function:backfill_injury_eta_fairness'),
      ('column:public.players.intensity_tier'),
      ('function:backfill_tier_fatigue_rebalance'),
      ('function:intensity_recovery_days'),
      ('function:repair_daily_drill_counts'),
      ('column:public.player_cards.in_academy'),
      ('column:public.player_cards.academy_progress'),
      ('column:public.player_cards.academy_seated_at'),
      ('column:public.players.scouting_finishes_at'),
      ('column:public.players.scouting_active_tier'),
      ('table:public.scouting_reports'),
      ('policy:public.scouting_reports.scouting_reports_select'),
      ('policy:public.scouting_reports.scouting_reports_insert'),
      ('policy:public.scouting_reports.scouting_reports_update'),
      ('function:academy_slot_cap'),
      ('function:promote_academy_player'),
      ('function:release_academy_player'),
      ('function:process_daily_academy_growth'),
      ('function:dispatch_youth_scout'),
      ('function:finalize_youth_scout_report'),
      ('function:sign_youth_scout_prospect'),
      ('policy:public.mentor_transfer_log.mentor_transfer_log_select'),
      ('policy:public.mentor_transfer_log.mentor_transfer_log_insert'),
      ('policy:public.league_members.league_members_select'),
      ('policy:public.league_matchday_reminders.league_matchday_reminders_select'),
      ('policy:public.league_matchday_reminders.league_matchday_reminders_insert'),
      ('policy:public.league_members.league_members_insert'),
      ('policy:public.league_matchday_manager_awards.league_matchday_manager_awards_select'),
      ('policy:public.league_matchday_manager_awards.league_matchday_manager_awards_insert'),
      ('policy:public.league_registrations.league_registrations_select'),
      ('policy:public.league_registrations.league_registrations_insert'),
      ('policy:public.league_matchdays.league_matchdays_select'),
      ('policy:public.league_matchdays.league_matchdays_insert'),
      ('policy:public.league_final_standings.league_final_standings_select'),
      ('policy:public.league_final_standings.league_final_standings_insert'),
      ('policy:public.league_operation_runs.league_operation_runs_select'),
      ('policy:public.league_operation_runs.league_operation_runs_insert'),
      ('policy:public.league_outbox.league_outbox_select'),
      ('policy:public.league_outbox.league_outbox_insert')
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
        WHEN 'league_dynamics_enabled' THEN to_regprocedure('public.league_dynamics_enabled()')
        WHEN 'league_automation_enabled' THEN to_regprocedure('public.league_automation_enabled()')
        WHEN 'league_lifecycle_v1_enabled' THEN to_regprocedure('public.league_lifecycle_v1_enabled()')
        WHEN 'award_manager_of_the_matchday' THEN to_regprocedure('public.award_manager_of_the_matchday(uuid,integer)')
        WHEN 'apply_seasonal_promotion_relegation' THEN to_regprocedure('public.apply_seasonal_promotion_relegation(uuid)')
        WHEN 'charge_league_entry_fees' THEN to_regprocedure('public.charge_league_entry_fees(uuid)')
        WHEN 'claim_weekly_rank_tier' THEN to_regprocedure('public.claim_weekly_rank_tier(bigint,text)')
        WHEN 'process_match_result' THEN to_regprocedure('public.process_match_result(text,uuid[],integer,numeric[],integer[],uuid)')
        WHEN 'acquire_match_lock' THEN to_regprocedure('public.acquire_match_lock(bigint,text)')
        WHEN 'release_match_lock' THEN to_regprocedure('public.release_match_lock(bigint)')
        WHEN 'increment_match_career_stats' THEN to_regprocedure('public.increment_match_career_stats(bigint,text,integer,integer,integer)')
        WHEN 'increment_league_career_stats' THEN to_regprocedure('public.increment_league_career_stats(bigint,text)')
        WHEN 'upsert_matchday_milestone_points' THEN to_regprocedure('public.upsert_matchday_milestone_points(uuid,bigint,integer,integer)')
        WHEN 'train_with_fodder' THEN to_regprocedure('public.train_with_fodder(bigint,uuid,uuid)')
        WHEN 'process_agent_sale' THEN to_regprocedure('public.process_agent_sale(bigint,uuid)')
        WHEN 'allocate_skill_point' THEN to_regprocedure('public.allocate_skill_point(bigint,uuid,text)')
        WHEN 'renew_contract' THEN to_regprocedure('public.renew_contract(bigint,uuid,bigint,integer)')
        WHEN 'cancel_player_evolution' THEN to_regprocedure('public.cancel_player_evolution(bigint,uuid)')
        WHEN 'process_stat_drill' THEN to_regprocedure('public.process_stat_drill(bigint,uuid,text)')
        WHEN 'claim_daily_pack' THEN to_regprocedure('public.claim_daily_pack(bigint,jsonb,timestamptz)')
        WHEN 'card_age_from_dob' THEN to_regprocedure('public.card_age_from_dob(date,date)')
        WHEN 'card_xp_age_multiplier' THEN to_regprocedure('public.card_xp_age_multiplier(integer)')
        WHEN 'retire_player_card' THEN to_regprocedure('public.retire_player_card(uuid)')
        WHEN 'process_season_aging' THEN to_regprocedure('public.process_season_aging()')
        WHEN 'training_ground_xp_bonus' THEN to_regprocedure('public.training_ground_xp_bonus(integer)')
        WHEN 'upgrade_club_facility' THEN to_regprocedure('public.upgrade_club_facility(bigint,text,bigint)')
        WHEN 'apply_match_fatigue' THEN to_regprocedure('public.apply_match_fatigue(bigint,jsonb,uuid[])')
        WHEN 'process_post_match_injuries' THEN to_regprocedure('public.process_post_match_injuries(bigint,jsonb)')
        WHEN 'process_daily_recovery' THEN to_regprocedure('public.process_daily_recovery()')
        WHEN 'admit_to_hospital' THEN to_regprocedure('public.admit_to_hospital(bigint,uuid)')
        WHEN 'discharge_from_hospital' THEN to_regprocedure('public.discharge_from_hospital(bigint,uuid)')
        WHEN 'insert_scouting_pool_player' THEN to_regprocedure('public.insert_scouting_pool_player(jsonb)')
        WHEN 'purchase_scouting_player' THEN to_regprocedure('public.purchase_scouting_player(bigint,uuid,bigint)')
        WHEN 'p2p_transfer_market_enabled' THEN to_regprocedure('public.p2p_transfer_market_enabled()')
        WHEN 'card_is_on_transfer_list' THEN to_regprocedure('public.card_is_on_transfer_list(uuid)')
        WHEN 'assert_card_not_on_transfer_list' THEN to_regprocedure('public.assert_card_not_on_transfer_list(uuid)')
        WHEN 'create_transfer_listing' THEN to_regprocedure('public.create_transfer_listing(bigint,uuid,bigint)')
        WHEN 'cancel_transfer_listing' THEN to_regprocedure('public.cancel_transfer_listing(bigint,uuid)')
        WHEN 'purchase_transfer_listing' THEN to_regprocedure('public.purchase_transfer_listing(bigint,uuid,bigint)')
        WHEN 'expire_stale_transfer_listings' THEN to_regprocedure('public.expire_stale_transfer_listings()')
        WHEN 'wages_payroll_enabled' THEN to_regprocedure('public.wages_payroll_enabled()')
        WHEN 'payroll_utc_week_key' THEN to_regprocedure('public.payroll_utc_week_key(timestamptz)')
        WHEN 'card_weekly_wage_coins' THEN to_regprocedure('public.card_weekly_wage_coins(integer,text)')
        WHEN 'club_xi_weekly_wage_bill' THEN to_regprocedure('public.club_xi_weekly_wage_bill(bigint)')
        WHEN 'card_contract_blocks_xi' THEN to_regprocedure('public.card_contract_blocks_xi(timestamptz)')
        WHEN 'assert_club_payroll_market_ok' THEN to_regprocedure('public.assert_club_payroll_market_ok(bigint)')
        WHEN 'process_club_weekly_payroll' THEN to_regprocedure('public.process_club_weekly_payroll(bigint,text)')
        WHEN 'process_weekly_payroll' THEN to_regprocedure('public.process_weekly_payroll(text)')
        WHEN 'process_youth_intake' THEN to_regprocedure('public.process_youth_intake(bigint,jsonb)')
        WHEN 'formation_slot_role' THEN to_regprocedure('public.formation_slot_role(text,integer)')
        WHEN 'transfer_mentor_xp' THEN to_regprocedure('public.transfer_mentor_xp(bigint,uuid,uuid,integer)')
        WHEN 'process_recovery_session' THEN to_regprocedure('public.process_recovery_session(bigint,uuid)')
        WHEN 'process_recovery_batch' THEN to_regprocedure('public.process_recovery_batch(bigint,uuid[])')
        WHEN 'prepare_support_legendary_reward' THEN to_regprocedure('public.prepare_support_legendary_reward(bigint,jsonb)')
        WHEN 'claim_support_legendary_reward' THEN to_regprocedure('public.claim_support_legendary_reward(bigint)')
        WHEN 'support_legendary_reward_pending' THEN to_regprocedure('public.support_legendary_reward_pending(bigint)')
        WHEN 'backfill_injury_eta_fairness' THEN to_regprocedure('public.backfill_injury_eta_fairness()')
        WHEN 'backfill_tier_fatigue_rebalance' THEN to_regprocedure('public.backfill_tier_fatigue_rebalance()')
        WHEN 'intensity_recovery_days' THEN to_regprocedure('public.intensity_recovery_days(integer,integer,integer)')
        WHEN 'repair_daily_drill_counts' THEN to_regprocedure('public.repair_daily_drill_counts()')
        WHEN 'academy_slot_cap' THEN to_regprocedure('public.academy_slot_cap(integer)')
        WHEN 'promote_academy_player' THEN to_regprocedure('public.promote_academy_player(bigint,uuid)')
        WHEN 'release_academy_player' THEN to_regprocedure('public.release_academy_player(bigint,uuid)')
        WHEN 'process_daily_academy_growth' THEN to_regprocedure('public.process_daily_academy_growth()')
        WHEN 'dispatch_youth_scout' THEN to_regprocedure('public.dispatch_youth_scout(bigint,text)')
        WHEN 'finalize_youth_scout_report' THEN to_regprocedure('public.finalize_youth_scout_report(bigint,jsonb,text)')
        WHEN 'sign_youth_scout_prospect' THEN to_regprocedure('public.sign_youth_scout_prospect(bigint,uuid,integer)')
        ELSE NULL
      END IS NOT NULL
    )
  );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Schema verify failed — missing: %', array_to_string(v_missing, ', ');
  END IF;

  -- apply_card_xp must be SECURITY DEFINER (migration 048) — existence alone is not enough
  IF NOT EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname = 'apply_card_xp'
      AND pg_get_function_identity_arguments(p.oid) = 'p_card_id uuid, p_xp_amount integer, p_source text'
      AND p.prosecdef
  ) THEN
    RAISE EXCEPTION 'Schema verify failed — apply_card_xp is not SECURITY DEFINER (apply migration 048)';
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
        'league_matchday_milestones', 'weekly_rank_rewards', 'scouting_pool_players',
        'pending_level_rewards', 'fusion_daily_log', 'player_drill_daily_log',
        'game_config', 'agent_sale_daily_log', 'energy_refill_daily_log',
        'hospital_patients', 'mentor_transfer_log',
        'transfer_listings', 'transfer_sales_log',
        'league_matchday_manager_awards',
        'league_registrations', 'league_divisions', 'league_matchdays',
        'league_final_standings', 'league_transition_journal',
        'league_operation_runs', 'league_outbox'
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

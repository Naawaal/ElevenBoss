# Contract: Job Catalog (US-42.8)

**Living document** — filled 2026-07-22 from `apps/discord_bot/main.py` scheduler registration.

## Entry schema

| Column | Meaning |
|--------|---------|
| `job_id` | Function name passed to `add_job` |
| `module` | Import / task module |
| `schedule_intent` | From `main.py` |
| `run_key` | Durable uniqueness |
| `catch_up` | On miss / restart |
| `notes` | Rulebook / RPC |

## Catalog

| job_id | module | schedule_intent | run_key | catch_up | notes |
|--------|--------|-----------------|---------|----------|-------|
| `season_aging_job` | `scheduler_jobs` / aging | cron Mon 00:00 UTC | RPC `process_season_aging` internal | Next wake runs RPC once | Decline lifecycle |
| `youth_intake_job` | `youth_intake_notifier` | cron Mon 00:00 UTC | `process_youth_intake` + week | Idempotent intake week | |
| `regen_pool_job` | `regen_pool_job` | cron Mon 00:00 UTC | insert pool / config | Re-run safe inserts | Scouting pool |
| `weekly_league_reset_job` | league reset task | cron Mon 00:00 UTC | week / season keys | Skip if already reset | Legacy/dynamics |
| `auto_sim_expired_fixtures_job` | `league_cog` auto-sim | interval 10 min | fixture `is_played` + active run skip | Catch overdue windows | US-42.4/42.5 |
| `league_matchday_reminder_job` | reminders | interval 1 h | reminder dedupe | Soft present | No economy |
| `daily_recovery_job` | `scheduler_jobs` | cron 00:05 UTC | `process_daily_recovery` day | One pass per club/day in RPC | Fatigue |
| `league_state_machine_job` | `league_automation` | cron 00:05 UTC | automation state | Idempotent transitions | |
| `league_lifecycle_wake_job` | lifecycle wake | interval 5 min | `league_operation_runs` / `_run_once` | Ordered catch-up | US-42.5 |
| `weekly_payroll_job` | payroll task | cron Mon 00:05 UTC | payroll week key in RPC | One week bill | 019 |
| `academy_growth_job` | `academy_growth_job` | cron 00:10 UTC | `process_daily_academy_growth` | Day key in RPC | |
| `transfer_listing_expiry_job` | `transfer_listing_expiry_job` | interval 1 h | `expire_stale_transfer_listings` batch `status=active AND expires_at<=now` | Re-run no-ops terminals | Soft: no per-listing key |

## Rules

1. Competitive outcomes not invented by cron alone — point at RPCs / `026`.
2. Double wake ≤1 durable mutation per run_key / natural uniqueness.
3. Compatible with US-42.5 league operation keys for lifecycle wakes.

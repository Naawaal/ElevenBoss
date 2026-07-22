# Contract: Job Claim Catalog (US-43 / FR-016)

**Parent**: [../spec.md](../spec.md) | Implementation: `apps/discord_bot/core/job_claims.py`

Keys use `league_operation_runs.operation_key` via `acquire_operation` (prefix `job:`).
Prefer `run_claimed_job(db, name, window, work)` in scheduler entry points.

| Job | Source | Window helper | Key example | Status |
|-----|--------|---------------|-------------|--------|
| `daily_recovery` | `scheduler_jobs.daily_recovery_job` | `utc_day_window` | `job:daily_recovery:2026-07-22` | wrapped |
| `weekly_payroll` | `scheduler_jobs.weekly_payroll_job` | `utc_week_window` | `job:weekly_payroll:2026-W30` | wrapped |
| `academy_growth` | `academy_growth_job` | `utc_day_window` | `job:academy_growth:{day}` | wrapped |
| `transfer_listing_expiry` | hourly | `utc_hour_window` | `job:transfer_listing_expiry:{hour}` | wrapped |
| `season_aging` | weekly Mon | `utc_week_window` | `job:season_aging:{week}` | wrapped |
| `youth_intake` | weekly | `utc_week_window` | `job:youth_intake:{week}` | wrapped |
| `regen_pool` | weekly | `utc_week_window` | `job:regen_pool:{week}` | wrapped |
| `weekly_league_reset` | weekly | `utc_week_window` | `job:weekly_league_reset:{week}` | wrapped |
| `league_state_machine` | daily | `utc_day_window` | `job:league_state_machine:{day}` | wrapped |
| `league_matchday_reminder` | hourly | `utc_hour_window` | `job:league_matchday_reminder:{hour}` | wrapped |
| `auto_sim_expired_fixtures` | 10m | prefer matchday/fixture keys | existing league ops | per-fixture (unchanged) |
| `league_lifecycle_wake` | 5m | existing `league_operation_runs` keys | already claimed per transition | unchanged |

## SC-006 drill

1. Start two bot processes sharing the same Supabase project.
2. Advance clock / trigger `daily_recovery_job` on both.
3. Expect one `process_daily_recovery` RPC effect; other logs `skipped — already claimed`.
4. Confirm single `league_operation_runs` row for `job:daily_recovery:{day}` with status `succeeded`.

Unit stand-in: `tests/test_job_claims.py::test_sc006_second_claim_skips_work`.

Do **not** enable multi-instance production deploy until the two-process drill passes.

# Contract: Registration Windows (Automation)

**Feature**: `021-league-automation-and-config`

## Pure helper — `next_monday_0005_utc(now) → datetime`

Return the next Monday at 00:05 UTC strictly after `now` if currently past that instant this week; if `now` is Monday before 00:05, return today’s 00:05.

## Pure helper — `registration_closes_at(opened_at, hours=48) → datetime`

`opened_at + timedelta(hours=hours)`.

## Pure helper — `can_open_auto_registration(now, next_at, has_active_or_reg) → bool`

False if has active/registration; false if `next_at` set and `now < next_at`; else true.

## Pure helper — `evaluate_registration_close(human_count, min_humans) → 'start' | 'fail_under_min'`

## Config

- Hours: `league_automation_registration_hours` (48)
- Min: `league_min_humans` (2)

## Persistence

- On open: `config_json.automation=true`, `registration_closes_at`
- On fail: clear registration season; `guild_config.next_auto_registration_at = next_monday_0005_utc`
- On successful start: clear `next_auto_registration_at`

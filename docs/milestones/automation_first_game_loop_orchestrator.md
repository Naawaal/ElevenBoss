# Milestone — Automation-First Game Loop Orchestrator

This document details the design, implementation, and features of the central orchestration layer controlling league lifecycle and scheduled matchday automation in ElevenBoss.

## Overview
ElevenBoss aims to minimize manual administrator interventions. The automated game loop moves the football world forward automatically wherever user-centric decisions are not required.

### Target Automation Flow
1. **Club Registration (`/register`):** Automatically detects if `auto_join_draft_league` is enabled. If a draft league exists and has available slots, the club is enrolled immediately.
2. **League Lifecycle Check:** Scans leagues periodically. If a draft league meets conditions (human count >= min human clubs AND (league is full OR registration deadline passed OR auto-fill with bot clubs enabled)), it starts automatically.
3. **Scheduled Matchday Simulation:** Using timezone-aware computations (`Asia/Kathmandu` default), the orchestrator triggers weekly match simulations when the scheduled time window arrives.
4. **League Standings and Season Week:** Atomically calculated and updated in single database transactions.
5. **Discord Announcements:** Results, start of leagues/seasons, and completions are announced in the configured channel. Discord channel posting failures are caught and logged without rolling back simulation transactions.

---

## Architectural Layout
We adhere to a strict clean layer boundary pattern:
* **Background Scheduler Check (`app/scheduler/scheduler.py`):** Runs an interval trigger (every 1-5 minutes).
* **Game Loop Orchestration (`app/services/game_loop_orchestrator.py`):** Scans all guilds connected to the bot, managing step validations and database updates.
* **Lifecycle Rules (`app/services/league_lifecycle_service.py`):** Evaluates draft league readiness.
* **Time & Scheduling (`app/services/schedule_service.py`):** Checks schedule times and handles timezone conversions via python `zoneinfo`.
* **Discord Announcements (`app/services/announcement_service.py`):** Transmits results, news, and completions to Discord channels safely.

---

## Configuration & Status Database Schema
The `guild_configs` table was expanded with the following fields:
* `auto_join_draft_league` (Boolean, default: `True`)
* `auto_start_league` (Boolean, default: `False`)
* `auto_fill_with_bot_clubs` (Boolean, default: `True`)
* `minimum_human_clubs` (Integer, default: `2`)
* `registration_deadline` (DateTime, nullable: `True`)
* `matchday_enabled` (Boolean, default: `False`)
* `matchday_day` (String, nullable: `True`)
* `matchday_time` (String, nullable: `True`)
* `matchday_timezone` (String, default: `Asia/Kathmandu`)
* `matchday_announcement_channel_id` (String, nullable: `True`)
* `automation_status` (String, default: `idle`)
* `last_automation_run_at` (DateTime, nullable: `True`)
* `last_automation_status` (String, nullable: `True`)
* `last_automation_error` (Text, nullable: `True`)

---

## Idempotency Protection
To avoid running duplicate or parallel matchday simulations, every check uses the job locking mechanism via `scheduler_runs`.
Keys follow the standard structures:
* `league_start:{guild_id}:{league_id}`
* `matchday:{guild_id}:{season_id}:{week}`
* `season_complete:{guild_id}:{season_id}`

---

## Implemented Commands

### User Commands
* `/automation status` - General view of the current league, season, current week, next scheduled matchday, last check results, and warnings (e.g. missed runs).

### Administrator Setup & Overrides
* `/setup status` - Visual panel containing the server's ElevenBoss setup.
* `/setup automation` - Configure auto-join, auto-start, auto-fill, and minimum human parameters.
* `/schedule status` - Detailed schedule settings (day, time, timezone) with next run estimates.
* `/schedule set` - Edit scheduled run day, time, and timezone.
* `/schedule enable` / `/schedule disable` - Toggle scheduled runner.
* `/schedule run-now` - Forces immediate match simulation for the current week.
* `/automation run-check` - Manually trigger orchestrator check on the guild now.

---

## Missed Run Catch-up Policy
If the bot goes offline, matchday simulations do not catch up silently. Instead:
1. A warnings alert is displayed inside `/schedule status` and `/automation status`.
2. Administrators can use `/schedule run-now` or `/automation run-check` to simulate the week's matches manually.

---

## Known Limitations
* Automatic daylight savings offset updates depend on python `zoneinfo` database definitions.
* Discord channel permission overrides may block announcements. However, this is shielded from the core simulation transaction.

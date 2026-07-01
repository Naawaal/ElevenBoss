# Milestone — Unified Settings Command System

This document outlines the consolidation, permission hierarchy, and Components V2 designs for the unified `/settings` and `/admin` command groups in ElevenBoss.

## Overview
To provide a clean, modern, and professional command interface, ElevenBoss has moved all configuration-oriented slash commands under `/settings` and all manual/emergency overrides under `/admin`.

### Consolidated Commands

#### Public Player Commands (Top-level)
* `/register`
* `/club`
* `/squad`
* `/lineup`
* `/fixtures`
* `/table`
* `/match`
* `/help`

#### Config Settings Command Group (`/settings`)
* `/settings overview` - Server-wide settings overview panel.
* `/settings channels-view` / `/settings channels-set` - Manage Game and Announcement channels.
* `/settings admin-role-view` / `/settings admin-role-set` / `/settings admin-role-clear` - Manage TwelveBoss admin role permissions.
* `/settings automation-view` / `/settings automation-set` - Configure auto-join, auto-start, auto-fill parameters.
* `/settings schedule-view` / `/settings schedule-set` / `/settings schedule-enable` / `/settings schedule-disable` - Configure cron schedules.
* `/settings matchday-view` - View weekly fixture simulation state details.

#### Emergency Overrides Command Group (`/admin`)
* `/admin dashboard` - Manual override control dashboard.
* `/admin matchday-run` - Simulates current matchweek.
* `/admin automation-check` - Manually checks lifecycle and schedule triggers.
* `/admin league-start` - Manually bootstraps draft leagues.

---

## Hardened Permission Model
We introduced [permission_service.py](file:///d:/Python/Discord/Bots/ElevenBoss/app/services/permission_service.py) with levels:
1. **Public User:** Allowed to view safe settings overview metrics.
2. **ElevenBoss Admin:** Has Discord Administrator permission or the configured role in `guild_configs.admin_role_id`. Can change channels, schedules, and automation parameters.
3. **Discord Administrator:** Only users with native Discord Administrator privileges can configure, set, or clear the ElevenBoss Admin role itself.

---

## Components V2 settings UI
Layout configurations reside in [settings.py](file:///d:/Python/Discord/Bots/ElevenBoss/app/ui/layouts/settings.py). Buttons let users pivot between subcategories (Channels, Admin Role, Automation, Schedule, Matchday) instantly.

---

## Backward Compatibility & Migration
The legacy cogs (`setup_cog.py`, `schedule_cog.py`, `automation_cog.py`, `matchday_cog.py`) have been completely deleted to keep command registration clean.

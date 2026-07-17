# Data Model: League Automation

**Feature**: `021-league-automation-and-config` | **Date**: 2026-07-15  
**Migration**: `065_league_automation.sql`

## Entities

### GuildConfig (`guild_config` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `league_channel_id` | BIGINT | Existing — announce channel |
| `announcement_role_id` | BIGINT | Existing — mention role |
| `league_status` | TEXT | Existing |
| `league_automation_enabled` | BOOLEAN NULL | NULL = inherit global; true/false override |
| `next_auto_registration_at` | TIMESTAMPTZ NULL | Under-min / cooldown: earliest next auto open (Monday 00:05 UTC) |
| `automation_last_error` | TEXT NULL | Optional ops hint for `/admin` (channel missing, etc.) |

### LeagueSeason (`league_seasons` — config_json conventions)

No new columns required if `config_json` is used:

| Key | Type | Notes |
|-----|------|-------|
| `automation` | bool | true = job-owned |
| `registration_closes_at` | ISO timestamptz string | Set at open |
| `last_digest_matchday` | int | Idempotent announce digests |
| `registration_failed_under_min` | bool | Optional audit |

`pacing_mode` from 020 remains source of tick math (`dynamics` for automation-owned starts).

### GameConfig keys (seed)

| Key | Default | Meaning |
|-----|---------|---------|
| `league_automation_enabled` | `false` | Global master flag |
| `league_automation_registration_hours` | `48` | Auto registration window length |
| `league_min_humans` | `2` | Already exists — reuse |

Helper: `league_automation_enabled() RETURNS BOOLEAN`.

### Not added

- `guilds` table / `league_announce_channel_id` aliases  
- New `division_tier` (020)  
- Parallel season status enum  

---

## State transitions (automation-owned)

```text
[idle / next_auto_registration_at]
  → (job, eligible, channel OK) OPEN registration (48h)
[registration] window open
  → (now >= closes_at, humans >= min) START dynamics season
  → (now >= closes_at, humans < min) FAIL → set next_auto_registration_at = next Monday 00:05 UTC
[active] daily 00:05
  → auto_sim → settle → digest (idempotent)
  → last MD complete → prizes/promo → OPEN registration (same run if channel OK)
[paused]
  → job skips tick/advance for that season
```

Manual seasons (`automation` absent/false): job never opens/starts for them; Dynamics tick still runs via folded job for `pacing_mode=dynamics`.

---

## Migration notes

1. ADD nullable guild columns with defaults NULL.  
2. Seed game_config keys.  
3. Do not rewrite active seasons’ windows.  
4. Extend `verify_required_schema.sql`.

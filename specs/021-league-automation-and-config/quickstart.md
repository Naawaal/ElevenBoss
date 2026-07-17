# Quickstart: League Automation Validation

**Feature**: `021-league-automation-and-config`  
**Date**: 2026-07-15

## Prerequisites

- Migrations **064** (Dynamics) + **065** (automation) applied  
- `verify_required_schema.sql` passes  
- Test guild: `/admin` announce channel + mention role set  
- Flags **off** initially  

## 1. Pure rules

```bash
pytest tests/test_league_automation_rules.py -q
```

Expect: Monday 00:05 helper; under-min → fail; can_open respects `next_auto_registration_at`.

## 2. Schema

```bash
python scratch/apply_migration_065.py
python scratch/verify_schema_full.py
```

Expect: `league_automation_enabled` false; guild columns; helpers.

## 3. Flag off

1. `/admin` still shows Open Registration / Start Season  
2. 00:05 job does not open autonomous registration  
3. Dynamics-only seasons (if any) still get midnight tick via folded job  

## 4. Enable automation (ops)

```sql
UPDATE game_config SET value_json = 'true'::jsonb WHERE key = 'league_automation_enabled';
-- optional per-guild:
UPDATE guild_config SET league_automation_enabled = true WHERE guild_id = <id>;
```

## 5. Admin gates

`/admin` → League Management: Open/Start hidden; Pause/Force End remain. Labels show League announce channel / mention role.

## 6. Happy path (pilot)

1. No active season; channel set → after 00:05 (or smoke invoke), registration opens with announce ping + 48h close.  
2. Register ≥ `league_min_humans` humans via `/league`.  
3. After close (+ job), season starts Dynamics 14 MD; schedule announce.  
4. Leave a fixture unplayed past midnight → next 00:05 sims + digest + MoMD rules.  
5. Force-complete or wait → prizes → new registration same/next cycle.

## 7. Under-min Monday path

1. Open auto registration; register 0–1 humans (below min).  
2. After close → fail announce; `next_auto_registration_at` = next Monday 00:05 UTC.  
3. Mid-week job does not reopen; Monday job opens fresh 48h.

## 8. Grandfather

Leave a manual `active` season unmarked; enabling flag does not rewrite its windows.

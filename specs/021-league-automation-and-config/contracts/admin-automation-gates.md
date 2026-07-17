# Contract: Admin Automation Gates

**Feature**: `021-league-automation-and-config`  
**Surface**: `/admin` → League Management + Announcement Settings

## Announcement Settings

Clarify copy:

- Channel → **League announce channel** (maps to `league_channel_id`)
- Role → **League mention role** (maps to `announcement_role_id`)

Show `automation_last_error` if set (ephemeral field on admin hub).

## League Management when automation **effective**

| Control | Visible / enabled |
|---------|-------------------|
| Open Registration | **No** |
| Start Season | **No** |
| Pause Season | **Yes** (active seasons) |
| Force End Season | **Yes** (active seasons) |
| Resume (if exists) | **Yes** when paused |

Footer note: “Lifecycle is automated. Use Pause / Force End for emergencies.”

## League Management when automation **off**

Existing buttons unchanged (Open / Start / Pause / End).

## Shared start core

`admin_start_season` becomes a thin wrapper calling:

`start_dynamics_season_from_registration(db, bot, guild, reg_season, *, automation: bool)`

Automation path always passes `automation=True` and Dynamics seating; manual path uses current flag/dynamics branching from 020.

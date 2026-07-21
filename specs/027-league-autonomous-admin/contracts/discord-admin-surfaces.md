# Contract: Discord Admin Surfaces

**Feature**: `027-league-autonomous-admin`  
**Amends**: `specs/026-league-lifecycle-rulebook/contracts/admin-and-hub-surfaces.md`

## `/admin` hub layout (normative)

| Branch | Purpose | Allowed |
|--------|---------|---------|
| **Announcements** | League announce channel + mention role | Presentation routing only |
| **Server Settings → League Time** | IANA timezone + local resolution hour | Future-season schedule preference only |
| **Switch Server** | Owner multi-guild select | Unchanged |

**Removed**: **League Management** submenu and all lifecycle/competitive controls previously under it.

## Forbidden Discord controls (must not exist)

No slash command, button, modal, or select may expose:

- Open / close registration
- Start season
- End / cancel / force-end season
- Pause / resume season
- Start or advance matchday
- Force-simulate fixtures
- Set season duration / league size / entry fees / prize values
- Add / remove / kick participants for competitive reasons
- Modify standings or scores
- Apply promotion / relegation
- Distribute or repeat rewards
- Run lifecycle / “run cycle now”
- Select legacy vs lifecycle mode / edit `league_lifecycle_v1_enabled` from Discord

## Inventory acceptance (SC-002)

After ship, grep/inventory of `admin_cog.py` persistent `custom_id`s MUST NOT include (examples of banned prefixes/ids):

- `league_admin_open_reg`
- `league_admin_config`
- `league_admin_start`
- `league_admin_end`
- `league_admin_kick`
- `league_admin_sim`
- `league_admin_duration`
- `league_admin_pause`
- `league_admin_run_cycle`

Allowed league-related admin ids are limited to Server Settings → League Time (new ids) plus existing Announcements channel/role flows.

## Player surface (unchanged authority)

- `/league hub` — register/withdraw when registration open; view + lineup prep only
- No player control of lifecycle transitions
- No new player slash commands

## Cutover

- Per-guild / global Lifecycle V1 enablement is **operator or `game_config` / DB only**
- Discord MUST NOT offer a mode picker or cutover field on League Time

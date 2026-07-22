# Contract: League Integrity Audit (W0)

**Feature**: US-42.5 | Filled from plan research 2026-07-22

## Critical (must fix)

| Gap | Location | Fix |
|-----|----------|-----|
| Unreachable pause omits `pause_started_at` | `guild_resolver.pause_season_if_guild_unreachable` | Set `pause_started_at` with status |
| Pause status filter too narrow | same + `pause_seasons_for_guild` | Include V1 open statuses (`registration_open`, `preparing`, …) |
| Paused Play copy says “admin resume” | `battle_cog` / league Play gates | Ops/server-available copy (`027`) |

## Soft

| Gap | Notes |
|-----|-------|
| `pause_season` only from `active` | Extend if preparing needs pause |
| Outbox announce exactly-once | Dedupe exists; harden if spam |
| Leave-guild explicit continuity message | Club already persists; optional UX |

## Already OK

- `_run_once` + `league_operation_runs` unique keys
- Fixture `is_played` skip on deadline resolve
- Active match run skip on auto-sim
- Prize economy keys `season_prize:{season}:{player}` + award ON CONFLICT
- Promo `config_json.promo_applied` short-circuit
- Humans-only prize loop (`is_ai = FALSE`)
- `on_guild_remove` → pause seasons
- US-42.3 soft register gate / US-42.4 Play settle-once

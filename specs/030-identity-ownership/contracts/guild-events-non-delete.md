# Contract: Guild Events Non-Delete

**Feature**: US-42.1 | **FR-010…012** | **Parent**: INV-01 durability

## Goal

Guild leave, bot remove, bot re-add, and guild delete/unreachable **never** delete `players` / `player_cards` as a side effect. Club is global; guild is context.

## Required behavior

| Event | Club / cards | League / config |
|-------|--------------|-----------------|
| User leaves guild | Persist | Lose membership-scoped eligibility (league overlay) |
| Bot `on_guild_remove` | Persist | `pause_seasons_for_guild(..., reason)` only |
| Bot re-added | Persist | Resume per `026`/`027` — no re-register |
| User joins new guild with bot | Same club | May use league in that guild |

## Code freeze points

- `apps/discord_bot/main.py` → `on_guild_remove` must call pause helper only.
- `apps/discord_bot/core/guild_resolver.py` → `pause_seasons_for_guild` must not delete players.
- Grep gate: no `table("players").delete` or `DELETE FROM players` in guild-remove/leave handlers.

## Tests / verification

1. Grep CI or quickstart checklist for delete-on-guild paths = 0 hits in event handlers.
2. Manual/smoke: remove bot from test guild → seasons paused; sample `players` row still present.

## Non-goals

- Rewriting league pause semantics (owned by 026/027).
- Per-guild club rows.

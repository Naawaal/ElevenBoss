# Contract: Admin and Hub Surfaces

**Feature**: `026-league-lifecycle-rulebook`  
**Discord authority amended by**: [`027-league-autonomous-admin`](../../027-league-autonomous-admin/contracts/discord-admin-surfaces.md)

> **027 policy (normative for Discord)**: Guild Discord admins configure **League Time only** (`/admin → Server Settings → League Time`). They MUST NOT start, stop, pause, advance, settle, force-simulate, or otherwise mutate lifecycle/competitive state from Discord. Operator recovery is non-Discord. See 027 contracts for the full inventory.

## Player surface

- **Keep** `/league hub` (register, standings, fixtures, scout, match center, early play).
- **No new** player slash commands for lifecycle.
- Hub shows next `window_end` as Discord local timestamp from frozen UTC.
- `/leaderboard` Season tab continues to read standings (finals when settled).
- Player actions supply input only while the engine has opened the relevant window — they do not control transition timing.

## Admin surface (`/admin`) — post-027

| Control | Behavior under V1 |
|---------|-------------------|
| **Server Settings → League Time** (IANA + local hour) | Guild preference for **future** seasons; frozen onto season at prepare; NULL coalesces to `UTC` / `00:00` without blocking |
| Announcements (channel / role) | Presentation routing only; must not block progression |
| Lifecycle mutators (open/start/pause/force-end/force-sim/kick/duration/run-cycle/mode select) | **Removed from Discord** (027). Engine remains sole authority; operator scripts may retry via the same engine |

## Presentation vs state

Announce channel, Journal, MatchDay threads consume **outbox** events. Missing channel / deleted thread MUST NOT block fixture or season settlement.

## Cutover

Exclusive per-guild Lifecycle cutover remains **operator / `game_config` / DB** — not a Discord mode picker.

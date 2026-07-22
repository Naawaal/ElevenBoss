# Contract: Club RPC Guard Audit Template

**Feature**: US-42.3 | **Wave W0**

## Purpose

Record whether club-entry / soft-lifecycle paths already enforce §B.5.

## Checklist (filled at implement)

| Path | Action | Soft Active gate | AI reject | MatchLocked | Idempotent seat | Gap? |
|------|--------|------------------|-----------|-------------|-----------------|------|
| `league_cog.player_register_league` (V1) | league_join | **Y** via `register_league_season` (076) | Y | Y (assert) | Y AlreadySeated | **Closed** |
| Legacy `register_league_membership` | league_join | **Y** via 076 | Y | Y | Y | **Closed** |
| `recover_club_identity` (074) | recover | — | — | — | Y | No |
| `classify_club_identity_status` (074) | classify | skips AI | — | — | Y | No |
| `touch_club_activity` (074) | qualify | auto-wake | — | — | Y | No |
| Bot fill `league_automation` | ai_fill | N/A | creates AI | — | system | No (unchanged) |

## Exit

Critical closed by migration `076` + league cog RPC wire.

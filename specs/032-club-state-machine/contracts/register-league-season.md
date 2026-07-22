# Contract: `register_league_season` RPC

**Feature**: US-42.3 | **Migration**: `076_club_state_guards.sql`

## Purpose

Atomic, idempotent seasonal league join with club-state enforcement — replaces cog-only Data API inserts as the write path for V1 registration.

## Target signature

```sql
register_league_season(
  p_player_id BIGINT,
  p_guild_id BIGINT,
  p_season_id UUID
) RETURNS JSONB
```

## Behavior

1. `PERFORM assert_club_action_allowed(p_player_id, 'league_join')`.
2. Validate season belongs to guild’s league and status is open for registration (`registration` / `registration_open`, `lifecycle_v1` as applicable).
3. If registration already `registered`/`locked` for `(season_id, player_id)` → return success AlreadySeated (idempotent).
4. Ensure `league_members` row exists (insert if missing).
5. Upsert `league_registrations` with status `registered` + eligibility snapshot fields the cog already collected (pass as jsonb arg if needed).
6. `PERFORM touch_club_activity(p_player_id)`.
7. Return `{status, season_id, player_id, already_seated}`.

## Eligibility (career matches / account age)

May remain pre-checked in cog **and/or** re-checked in RPC using existing config helpers — RPC MUST at least enforce club soft/kind/lock; re-checking min matches/days inside RPC is preferred fail-closed.

## Cog wiring

`league_cog.player_register_league` calls this RPC after defer; maps exceptions to ephemeral embeds.

## Non-goals

- Preparation seating / bot fill (`026` automation)
- Mid-season withdraw redesign
- Permanent-only `league_members` join without season (legacy path may keep thin assert or share helper)

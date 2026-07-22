# Research: Club State Machine (US-42.3)

**Date**: 2026-07-22 | **Feature**: `032-club-state-machine`

## R1 — Soft lifecycle storage

**Decision**: Reuse US-42.1 columns (`identity_status`, `last_qualifying_activity_at`, `identity_status_changed_at`) and RPCs (`touch_club_activity`, `classify_club_identity_status`, `recover_club_identity`). Do **not** add a second `club_status` column.

**Rationale**: Spec FR-001/002 align with 30/90 defaults already shipped in 074 + `identity.py`. Parallel columns would split-brain.

**Alternatives considered**: New `club_lifecycle` enum table — rejected (YAGNI, duplicate SoT).

## R2 — LeagueSeated modeling

**Decision**: Treat LeagueSeated as an **overlay** derived from `league_registrations` (season×player, status registered/locked) and/or `league_members` for legacy permanent join — not a soft primary.

**Rationale**: Spec FR-007; epic §5.2 clarification. Soft Active/Inactive/Abandoned must coexist with mid-season seat (FR-010: no mid-season kick solely for Inactive).

**Alternatives considered**: Exclusive primary “LeagueSeated” replacing Active — rejected (breaks soft recovery semantics).

## R3 — League join enforcement

**Decision**: Today `league_cog.player_register_league` writes `league_members` / `league_registrations` via Data API. US-42.3 introduces atomic RPC `register_league_season(p_player_id, p_guild_id, p_season_id)` (signature may vary) that calls `assert_club_action_allowed(..., 'league_join')`, enforces Human + Active, MatchLocked block, eligibility snapshots optional, upserts registration with UNIQUE `(season_id, player_id)`.

**Rationale**: FR-006/008 require server enforcement; cog inserts are presentation-adjacent and skip soft status today.

**Alternatives considered**: Cog-only `if identity_status != active` check — rejected as sole enforcer (UI rule). Full rewrite of `026` preparation — out of scope.

## R4 — AI kind

**Decision**: Continue using `players.is_ai`. Classify already skips AI (074). Assert blocks human hub actions including `league_join` for `is_ai`. Bot fill remains system path in `league_automation` (unchanged calendar).

**Rationale**: INV-15 + existing column; no new kind table.

## R5 — MatchLocked

**Decision**: `assert_club_action_allowed` calls `assert_not_in_match` for mutation actions per matrix (including `league_join`). Do not redefine lock acquire/release (US-42.4).

**Rationale**: INV-17 already implemented; club matrix cites it.

## R6 — Qualifying activity

**Decision**: Keep touch on economy success path (already wired). League join success should `touch_club_activity`. View-only hubs must not touch. Explicit `recover_club_identity` remains.

**Rationale**: Spec US5 / FR-005; avoid inventing a second activity pipe.

## R7 — Migration number

**Decision**: Next forward migration **`076_club_state_guards.sql`** (075 = player card state).

## R8 — Scheduler classify batch

**Decision**: MVP = on-demand classify (existing RPC) + gates on join; optional APScheduler batch classify deferred unless audit shows stale labels blocking ops.

**Rationale**: YAGNI; labels can be refreshed at join via `classify_club_identity_status` before assert.

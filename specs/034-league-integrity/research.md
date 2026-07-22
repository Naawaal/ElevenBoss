# Research: League Integrity (US-42.5)

**Date**: 2026-07-22 | **Feature**: `034-league-integrity`

## R1 — Ownership split (frozen)

**Decision**: `026`/`027` own sporting rules and League Time; this child only closes **integrity gaps** (pause metadata, idempotency acceptance, seat/AI bounds, copy). No second calendar.

**Rationale**: Epic §4.5; spec FR-001.

**Alternatives considered**: Merge calendar rewrite into 42.5 — rejected (duplication / drift).

## R2 — Pause must set `pause_started_at`

**Decision**: All pause entry points (`pause_season`, `pause_season_if_guild_unreachable`, `pause_seasons_for_guild`) MUST set `status=paused` **and** `pause_started_at=NOW()` when transitioning into paused. `resume_season` already rebases windows using `pause_started_at` and no-ops if null — unreachable pauses today can strand seasons without rebase.

**Rationale**: Spec FR-006/007; Critical audit gap in `guild_resolver.pause_season_if_guild_unreachable` (status-only update).

**Alternatives considered**: Infer pause start from journal — fragile. Skip rebase on unreachable — violates `026` SC-007 class.

## R3 — Pause status filter

**Decision**: Unreachable pause MUST target all non-terminal open statuses used in V1 (`active`, `registration_open`, `registration_locked`, `preparing`, and legacy `registration` if still present) — not only `active`/`registration`. Align `pause_season` helper similarly where safe (at least `active` + preparing if mid-cycle).

**Rationale**: Current filter misses V1 status vocabulary → seasons keep advancing while guild is gone.

## R4 — Transition idempotency (keep `_run_once`)

**Decision**: Keep `league_operation_runs` unique `operation_key` + `_run_once` / retryable delete pattern. Do not invent a second job ledger (US-42.8 owns global catalog later). Add regression tests that double-wake no-ops succeeded keys.

**Rationale**: Already correct architecture; Soft gaps are incomplete keys or post-success partials — audit per transition.

## R5 — Prize / promo once (mostly OK)

**Decision**: Keep `distribute_season_prizes` economy keys `season_prize:{season_id}:{player_id}` and refund keys; awards `ON CONFLICT DO NOTHING`; promo `config_json.promo_applied`. Add source/SQL guards asserting humans-only loop (`is_ai = FALSE`) and key patterns. Fix only if audit finds a path that pays without keys.

**Rationale**: INV-04/05/15; coins already protected under replay.

## R6 — Absence vs outage

**Decision**: Deadline path continues to use assistant / forfeit-if-illegal (`026`); outage → pause (R2), never mass forfeit. Human Play + deadline: skip when `is_played` or active match run (US-42.4).

**Rationale**: Spec B.3 / FR-008/009.

## R7 — Leave guild

**Decision**: No hard delete on member leave (none found today — club persists). Document as intentional; soft test that leave handlers never call club delete. Mid-season assistant continuity stays `026`. Soft Inactive registration gate stays US-42.3.

**Rationale**: Spec FR-011; YAGNI — don’t add member-remove forfeit logic.

## R8 — Manager copy

**Decision**: Replace “Wait for admin to resume” on paused Play with copy that season is paused / will resume when the server is available (ops path, not Discord admin) — aligns `027`.

**Rationale**: Spec US5 / FR-015/016.

## R9 — Migration 078

**Decision**: Default = **no schema** if Python pause fix suffices. Add **078** only if we need a single `pause_league_season(p_season_id, p_reason)` RPC enforcing `pause_started_at` + status whitelist for all callers.

**Rationale**: YAGNI; next number after `077`.

## R10 — Soft deferred

| Soft | Notes |
|------|-------|
| Outbox presentation exactly-once announce | Dedupe keys exist; harden only if spam observed |
| Global job catalog | US-42.8 |
| Economy faucet registry row for prizes | US-42.7 |
| Exhaustive edge matrix | US-42.10 |

# Implementation Plan: Club State Machine (US-42.3)

**Branch**: `032-club-state-machine` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/032-club-state-machine/spec.md`

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: `specs/030-identity-ownership` (US-42.1) | **Overlays**: `026`/`027` (sport only), `031` (cards stay separate)

## Summary

Make every **club-scoped** gate obey soft lifecycle (Active/Inactive/Abandoned), Human vs AI kind, LeagueSeated overlay bounds, and MatchLocked — via a pure club matrix module, shared SQL `assert_club_action_allowed`, and an **atomic league-join RPC** replacing cog-only inserts for seasonal registration. Reuse US-42.1 identity columns/RPCs (30/90d); do not invent a parallel status column. No second league calendar; no player-card matrix rewrite; no new slash commands.

**Technical approach**: (1) `packages/player_engine/club_state.py` — soft status + overlays + `can_perform_club_action` mirroring §B.5. (2) Migration **`076_club_state_guards.sql`** — `assert_club_action_allowed` + `register_league_season` (or equivalent) that enforces Active-only new joins, idempotent already-seated, AI reject, MatchLocked. (3) Point `league_cog.player_register_league` at the RPC. (4) Gap audit other club-entry paths. (5) pytest + smoke.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: US-42.1 RPCs (`touch_club_activity`, `classify_club_identity_status`, `recover_club_identity`); `players.is_ai`, `identity_status`, `last_qualifying_activity_at`; `league_registrations` / `league_members` (070); `assert_not_in_match`; `packages/player_engine`

**Storage**: No new soft-status column (reuse 074). Migration **076** adds assert + league-join RPC; extend `verify_required_schema.sql`. Optional `game_config` keys only if thresholds leave code constants (prefer keep 30/90 in sync with `identity.py`).

**Testing**: Parameterized pytest for club matrix + soft classify reuse; SQL/source greps for assert/join RPC; smoke Inactive→league_join Block

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo integrity child (`packages/player_engine` + `supabase/migrations` + thin cog/RPC wrapper)

**Performance Goals**: Assert is one locked club row + cheap overlay lookups inside existing txn

**Constraints**: Constitution + US-42 — no `discord` in packages; single XP/economy pipes; no new hubs; YAGNI — don’t rewrite `026` calendars or mid-season forfeit tables; don’t kick seated Inactive mid-season

**Scale/Scope**: 1 migration; 1 pure module (+ thin `club_rpc` helper); league cog path swap; tests for matrix + join gate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Matrix in `packages/player_engine`; Discord only presents / calls RPC |
| II. DB via RPC | PASS | League join moves to atomic RPC; assert in SQL |
| III. Typing / Pydantic | PASS | Typed literals / small result types in pure module |
| IV. Slash + defer | PASS | No new commands; existing league hub keeps defer |
| V. APScheduler | PASS | Batch classify optional later; on-demand classify already exists (074) |
| VI. Friendly errors | PASS | `CLUB_STATE:` reason families |
| VII. YAGNI | PASS | Reuse identity columns; one assert + one join RPC |

**Post-Phase 1 re-check**: PASS — contracts freeze assert/join APIs; no unjustified packages.

## Project Structure

### Documentation (this feature)

```text
specs/032-club-state-machine/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── club-state-derive.md
│   ├── club-action-matrix.md
│   ├── sql-assert-club-action.md
│   ├── register-league-season.md
│   └── club-rpc-guard-audit.md
├── checklists/requirements.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/club_state.py
packages/player_engine/player_engine/__init__.py   # export club helpers

supabase/migrations/076_club_state_guards.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_076.py
scratch/smoke_club_state_076.py

apps/discord_bot/core/club_rpc.py                 # thin wrappers
apps/discord_bot/cogs/league_cog.py               # call register_league_season RPC

tests/test_club_state_matrix.py
tests/test_club_state_sql_guards.py
# extend tests/test_identity_lifecycle.py only if needed for soft+join coupling
```

**Structure Decision**: Soft lifecycle SoT stays US-42.1 columns/RPCs. US-42.3 adds **club action matrix** (pure + SQL) and **server-enforced league join**. Card busy remains `031` / `assert_card_action_allowed`.

## Complexity Tracking

> No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Waves

| Wave | Scope | Exit |
|------|-------|------|
| **W0** | Audit league join + human-only paths vs §B.5 (`club-rpc-guard-audit.md`) | Gap list (join cog path = Critical) |
| **W1** MVP | Pure `club_state.py` + matrix tests | Pure suite green |
| **W2** | Migration 076 assert + `register_league_season`; wire league cog | Inactive/Abandoned cannot newly register; AI reject; idempotent seat |
| **W3** | Touch/recover/classify already OK — ensure join path doesn’t skip Active gate; optional profile soft badge skip | SC-003 class |
| **W4** | Smoke + `change_log.md` if managers see new join blocks; Lock spec | Docs + verify |

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Reuse 074; LeagueSeated overlay; atomic join RPC |
| [data-model.md](./data-model.md) | Soft primary + overlays + action codes |
| [contracts/](./contracts/) | Derive/matrix/assert/join/audit |
| [quickstart.md](./quickstart.md) | Validate W0–W4 |

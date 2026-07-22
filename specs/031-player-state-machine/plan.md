# Implementation Plan: Player State Machine (US-42.2)

**Branch**: `031-player-state-machine` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/031-player-state-machine/spec.md`

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: `specs/030-identity-ownership` (US-42.1)

## Summary

Make every player-card mutation obey one **derived primary exclusive state** plus **MatchLocked** overlay and documented modifiers — via a pure derive/matrix package, a shared SQL `assert_card_action_allowed` (or equivalent) used by mutating RPCs, gap-fix audits against the §B.5 matrix, and parameterized tests. No new slash commands; no XP/economy pipe rewrites; marketplace race depth stays US-42.6; match settlement wiring stays US-42.4.

**Technical approach**: (1) `packages/player_engine/card_state.py` — `derive_primary_state`, overlays/modifiers, `can_perform_action` mirroring spec matrix. (2) Migration **`075_player_card_state_guards.sql`** — central assert helper(s) + wire into highest-risk RPCs with gaps. (3) Grep audit vs matrix; fix missing guards only. (4) Optional thin hub reason mapping. (5) pytest matrix coverage (SC-001).

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: Existing RPCs (`assert_not_in_match`, `assert_card_not_on_transfer_list`, evolution/hospital/academy/squad RPCs); `packages/player_engine`; discord hubs for presentation only

**Storage**: No new card “state enum” column required for MVP (derive from existing flags/tables). Migration **075** adds shared assert function(s) and patches RPC bodies that miss matrix cells. Extend `verify_required_schema.sql`.

**Testing**: Parameterized pytest for derive + matrix cells; SQL/source greps for assert call sites; optional smoke for MatchLocked + Listed blocks

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo integrity child (`packages/player_engine` + selective `supabase/migrations` + light cog/view reason mapping)

**Performance Goals**: Derive is O(1) flag reads; assert adds one locked check per mutation — keep inside existing transactions

**Constraints**: Constitution + US-42 — no `discord` in packages; single XP/economy pipes; no new hubs/commands; YAGNI — consolidate asserts, don’t rewrite every RPC from scratch if already correct; InAcademy is exclusive (spec FR-020)

**Scale/Scope**: 1 migration; 1 pure module; audit + targeted RPC patches; tests covering exclusive pairs + key matrix cells

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Derive/matrix in `packages/player_engine`; Discord presentation only |
| II. DB via RPC | PASS | Enforcement in SQL asserts inside mutating RPCs |
| III. Typing / Pydantic | PASS | Typed literals / small result tuples in pure module |
| IV. Slash + defer | PASS | No new commands |
| V. APScheduler | PASS | No new jobs required (orphan reconcile optional later) |
| VI. Friendly errors | PASS | Stable reason families from assert |
| VII. YAGNI | PASS | Shared assert + pure mirror; no parallel state table |

**Post-Phase 1 re-check**: PASS — contracts define assert API and audit checklist; no unjustified packages.

## Project Structure

### Documentation (this feature)

```text
specs/031-player-state-machine/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── card-state-derive.md
│   ├── action-matrix.md
│   ├── sql-assert-card-action.md
│   └── rpc-guard-audit.md
├── checklists/requirements.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/card_state.py
packages/player_engine/player_engine/__init__.py

supabase/migrations/075_player_card_state_guards.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_075.py
scratch/smoke_player_card_state_075.py

# Targeted patches only where audit finds gaps, e.g.:
# supabase/migrations/075_... (CREATE OR REPLACE of process_stat_drill, start_player_evolution,
#   admit_to_hospital, create_transfer_listing, squad swap RPCs, … — only if missing asserts)

apps/discord_bot/                           # optional: map reason codes in hubs (minimal)

tests/test_card_state_derive.py
tests/test_card_state_matrix.py
tests/test_card_state_sql_guards.py        # migration source / assert presence greps
```

**Structure Decision**: Pure package is source of truth for *readable* matrix; SQL assert is source of truth for *enforcement*. Keep existing flag columns — do not add redundant `primary_state` column unless audit proves derive too error-prone (rejected for MVP).

## Complexity Tracking

> No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Waves

| Wave | Scope | Exit |
|------|-------|------|
| **W0** | Grep audit RPC guards vs matrix (`contracts/rpc-guard-audit.md`) | Gap list prioritized |
| **W1** MVP | Pure `card_state.py` + derive/matrix tests (SC-001/005) | Pure suite green |
| **W2** | Migration 075 shared `assert_card_action_allowed` + wire critical gaps | Listed/Hospital/Evo/MatchLocked blocks proven |
| **W3** | Remaining RPC patches from audit; MatchLocked coverage | SC-003 class |
| **W4** | Optional hub reason polish; quickstart; Lock spec | Docs + smoke |

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Pure-first, no state column, 075 assert design |
| [data-model.md](./data-model.md) | Derive inputs from existing columns/tables |
| [contracts/](./contracts/) | Derive API, matrix freeze, SQL assert, audit template |
| [quickstart.md](./quickstart.md) | Validate W0–W4 |

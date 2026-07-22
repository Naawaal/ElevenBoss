# Implementation Plan: Identity & Ownership (US-42.1)

**Branch**: `030-identity-ownership` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/030-identity-ownership/spec.md`

**Parent**: `specs/029-game-integrity` (US-42)

## Summary

Freeze and enforce **one Discord user → one human club**, durable ownership across guild leave / bot remove / re-add, current-owner card claims (INV-14), and soft Inactive/Abandoned labels without hard delete — by hardening `register_new_player` concurrency, documenting/guarding non-delete on guild events, adding minimal lifecycle columns + classify/touch helpers, and regression tests. No new slash commands; no multi-club; no XP/economy pipe changes.

**Technical approach**: Forward migration **`074_identity_ownership.sql`** (concurrent-safe register, soft lifecycle columns, classify/recover/touch RPCs, schema guards). Pure thresholds in `packages/player_engine`. Thin app wiring: onboarding already maps `ALREADY_REGISTERED`; optional activity touch from existing mutation wrappers; verify `on_guild_remove` never deletes clubs. Tests under `tests/` for register race + lifecycle math + claim-owner contract.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async, pydantic; `packages/player_engine`, existing `register_new_player`, `claim_pending_level_rewards`, `pause_seasons_for_guild`, `ensure_registered`

**Storage**: Supabase — alter `players` (soft lifecycle fields); replace `register_new_player` body for race safety; new small RPCs; extend `verify_required_schema.sql`. **No** new player-facing tables beyond columns on `players`. Next migration number after `073`.

**Testing**: pytest — concurrent/double register (SC-001), lifecycle threshold classify (pure), claim uses current owner (unit/contract), grep guards that guild-remove path does not `DELETE FROM players`

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo integrity child (`packages/player_engine` + `apps/discord_bot` + `supabase/migrations`)

**Performance Goals**: Register remains one RPC; classify job (if any) is batch-friendly; touch activity is O(1) upsert/update per mutation when wired

**Constraints**: Constitution + AGENTS + US-42 — no `discord` in packages; single economy/XP pipes untouched; no hard delete; no ownership transfer; no new slash commands; YAGNI — soft labels + harden existing paths, defer heavy abandonment automation polish to US-42.3 if needed

**Scale/Scope**: 1 migration; small pure module; light cog/middleware touches; tests; SDD pointer optional

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Thresholds/classify pure in `packages/player_engine`; Discord in `apps/discord_bot` |
| II. DB via RPC | PASS | Register/classify/touch/recover via RPCs; no cog multi-step club create |
| III. Typing / Pydantic | PASS | Optional small models for classify result |
| IV. Slash + defer | PASS | Existing `/register` + `ensure_registered` only |
| V. APScheduler | PASS | Optional thin classify wake later; not required for MVP if classify is on-read or manual RPC |
| VI. Friendly errors | PASS | Keep `ALREADY_REGISTERED` mapping; clear recover copy |
| VII. YAGNI | PASS | No multi-club, wipe tooling, or new hubs |

**Post-Phase 1 re-check**: PASS — design adds columns + RPC harden only; league pause remains in `guild_resolver`; no unjustified packages.

## Project Structure

### Documentation (this feature)

```text
specs/030-identity-ownership/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── register-idempotency.md
│   ├── guild-events-non-delete.md
│   ├── soft-lifecycle.md
│   └── ownership-current-owner.md
├── checklists/requirements.md
└── tasks.md                 # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/074_identity_ownership.sql
supabase/scripts/verify_required_schema.sql
scratch/apply_migration_074.py
scratch/smoke_identity_ownership_074.py

packages/player_engine/player_engine/identity.py   # thresholds, classify pure
packages/player_engine/player_engine/__init__.py    # export

apps/discord_bot/cogs/onboarding_cog.py            # confirm ALREADY_REGISTERED / unique race messaging
apps/discord_bot/middleware/guard.py               # ensure_registered unchanged semantically
apps/discord_bot/core/guild_resolver.py            # verify pause-only; comment/guard
apps/discord_bot/main.py                           # on_guild_remove already pause-only (verify)
apps/discord_bot/core/economy_rpc.py               # optional: touch activity after successful economy (thin)
# OR apps/discord_bot/core/identity_rpc.py         # wrappers for classify/recover/touch

tests/test_register_idempotency.py
tests/test_identity_lifecycle.py
tests/test_pending_rewards_current_owner.py       # extend or new if missing
```

**Structure Decision**: Keep identity helpers in `player_engine` (not a new package). Soft lifecycle is columns on `players`, not a parallel identity table. Guild events stay pause-only in existing resolver.

## Complexity Tracking

> No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Waves

| Wave | Scope | Exit |
|------|-------|------|
| **W0** | Audit: PK, `ALREADY_REGISTERED`, claim owner, guild remove grep | Gaps listed vs contracts |
| **W1** MVP | Migration 074 register race harden + tests SC-001 | Concurrent register ≤1 club |
| **W2** | Soft lifecycle columns + pure classify + recover RPC | Labels without delete |
| **W3** | Activity touch (minimal wiring) + guild non-delete contract smoke | SC-002 class |
| **W4** | Docs: change_log if player-visible; reconcile US-01 pointer | Quickstart green |

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Race fix, soft columns, deferrals |
| [data-model.md](./data-model.md) | `players` lifecycle fields |
| [contracts/](./contracts/) | Register, guild events, lifecycle, ownership |
| [quickstart.md](./quickstart.md) | Validate W0–W4 |

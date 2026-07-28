# Implementation Plan: Fix Contract Renew Stuck After First Renewal

**Branch**: `047-fix-contract-renew` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/047-fix-contract-renew/spec.md`

**US citation**: Hotfix for Implemented `019` contract renew. Economy path remains **`apply_club_economy` only** (**US-42** / INV coin pipe). No parallel coin UPDATE.

## Summary

`renew_contract` permanently keys economy idempotency as `contract_renewal:{card_id}`, so a second renew is a **replay success with no expiry extension**. Replace with a **per-attempt** key (minute-bucketed server default + optional client key), keep age/ownership/cost rules, and make `/player-profile` success copy depend on a real post-renew expiry (not a blind `True`).

Stuck cards (e.g. Roy Thompson) recover by renewing again after migration — no ledger delete required.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: Existing `renew_contract`, `apply_club_economy`, `player_cog` profile renew, `get_game_config_int`

**Storage**: Forward migration `087_fix_contract_renew_idempotency.sql` — `CREATE OR REPLACE` / drop-recreate `renew_contract` only; **no** new tables/columns

**Testing**: SQL/RPC smoke via scratch apply + verify; optional small pure/bot assertion that success path checks expiry; Discord smoke on stuck card

**Target Platform**: Hosted Supabase + Discord bot (Render)

**Project Type**: Hotfix (migration + thin Discord UI honesty)

**Performance Goals**: Single RPC + one post-renew card select; no loops

**Constraints**: Constitution II (RPC); AGENTS §3b (new migration file); YAGNI — no bulk renew command; do not weaken age ≥35 gate

**Scale/Scope**: 1 migration + `player_cog.py` renew callback + tests/changelog/quickstart; optional unique button `custom_id`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | SQL in migrations; Discord UI in `apps/discord_bot/` only |
| II. DB via RPC | PASS | Coin debit only via `apply_club_economy` inside `renew_contract` |
| III. Typing | PASS | Existing Python types; RPC return stays BOOLEAN unless plan upgrades to JSONB |
| IV. Slash + defer | PASS | Existing `/player-profile` renew button; defer already present |
| V. APScheduler | PASS | Untouched |
| VI. Friendly errors | PASS | Fail if renew “succeeds” but expiry still past grace |
| VII. YAGNI | PASS | Key format fix + UI honesty; no new surface |

**Post-Phase 1 re-check**: PASS — contracts forbid permanent per-card keys and false-success UI; no schema tables added.

## Project Structure

### Documentation (this feature)

```text
specs/047-fix-contract-renew/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── renew-idempotency.md
│   └── renew-profile-ui.md
└── tasks.md                 # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
supabase/migrations/087_fix_contract_renew_idempotency.sql   # NEW
scratch/apply_migration_087.py                                 # NEW (follow 086 pattern)
supabase/scripts/verify_required_schema.sql                    # touch only if signature guard needs update

apps/discord_bot/cogs/player_cog.py                            # renew_callback: post-check expiry + honest copy

tests/test_contract_renew_fix.py                             # NEW — document expected key behaviour / UI guard helpers if any
# or extend an existing wages/contract test if present

change_log.md                                                  # player-facing renew fix note
```

**Structure Decision**: Hotfix only — no new packages. Agent-context script absent — skipped.

## Complexity Tracking

> No constitution violations.

| Choice | Why | Simpler alternative rejected |
|--------|-----|------------------------------|
| Minute-bucketed server key (+ optional `p_idempotency_key`) | Unblocks lifetime re-renew; double-tap safe in same minute | Keep permanent card key (broken) |
| Keep `RETURNS BOOLEAN` + bot re-fetch expiry | Smallest Discord diff for honest UI | JSONB return (more churn, optional later) |
| No ledger backfill/delete | New keys ignore old permanent rows; players self-heal | Manual DELETE of ledger rows (risky, unnecessary) |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Implementation sketch (for tasks handoff)

1. Author `087_fix_contract_renew_idempotency.sql`:
   - `DROP FUNCTION IF EXISTS public.renew_contract(bigint, uuid, bigint, integer);`
   - Recreate with optional `p_idempotency_key TEXT DEFAULT NULL`
   - Effective key: `COALESCE(NULLIF(trim(p_idempotency_key), ''), 'contract_renewal:' || p_card_id::text || ':' || to_char(date_trunc('minute', timezone('utc', now())), 'YYYYMMDDHH24MI'))`
   - On economy `replay`: still `RETURN TRUE` (same-minute retry) — bot verifies expiry
   - Preserve age ≥35, ownership, extend-from-now-if-expired logic
   - `GRANT` + schema guard for function signature
2. `scratch/apply_migration_087.py` + verify
3. `player_cog.renew_callback`: pass optional uuid key per click; after RPC, reload `contract_expires_at`; if still past grace (using `contract_blocks_xi` / grace config), show error; else success with new expiry
4. Tests + `change_log.md`
5. Smoke: renew Roy Thompson on Crimson FC

# Implementation Plan: Mentor Transfusion

**Branch**: `006-mentor-transfusion` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-mentor-transfusion/spec.md`

## Summary

Give potential-maxed cards a purpose: convert surplus skill points into mentor units that grant XP to a same-club non-maxed card (**5 SP → 1 MP → 500 XP**), paced at **3 transfers per club per UTC day**. Surface discovery on `/development` Allocate Skills (and Mentor Ready copy on player profile). Reuse the single XP pipe `apply_card_xp`; do not touch match sim, coins, energy, marketplace formulas, or league LP.

**Technical approach**: (1) Pure conversion/eligibility in `packages/player_engine/mentor_math.py`; (2) migration `052` — append-only `mentor_transfer_log` + atomic RPC `transfer_mentor_xp`; (3) Development UI branch for maxed sources (target → amount → confirm); (4) profile Ready copy; (5) map RPC errors in `api_errors.py`. Deploy migration + verify before bot UI.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: pydantic ≥2.0, discord.py ≥2.7, supabase async client, local `player_engine`

**Storage**: Supabase Postgres — new table `mentor_transfer_log`; new RPC `transfer_mentor_xp`; calls existing `apply_card_xp` with source `'mentor_transfer'`

**Testing**: pytest — mentor math conversion/eligibility/headroom; optional SQL contract notes in quickstart

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — pure package math + Discord UI + SQL RPC

**Performance Goals**: Single RPC round-trip per confirm; Discord defer before DB; preview uses pure `simulate_apply_card_xp` (no write)

**Constraints**: AGENTS.md — no `discord` in `packages/`; no XP/coin bypasses; columns/RPCs only via migrations; extend `/development` + profile only; verify schema before bot ship; `change_log.md` on ship; reconcile `.specify/specs/v1.0.0/` on implement

**Scale/Scope**: ~8–12 files; 1 migration; 1 new pure module; Development + profile UI only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | `mentor_math.py` pure; views/cogs in `apps/discord_bot` |
| II. DB mutations via RPC | PASS | One atomic `transfer_mentor_xp`; no app-level multi-update loops |
| III. Typing / Pydantic at boundaries | PASS | Pure helpers + dataclass/result types for preview; RPC JSON mapped in bot |
| IV. Slash + defer | PASS | No new slash command; mentor callbacks defer immediately |
| V. APScheduler | PASS | No new jobs; daily cap is UTC date on log rows |
| VI. User-friendly errors | PASS | RPC exceptions → `api_errors` manager copy |
| VII. YAGNI | PASS | No flag service, no new SP columns, no profile CTA button, no position lock |

**Post-Phase 1 re-check**: PASS — contracts cover RPC, UI flow, math; single XP pipe preserved; additive schema only.

## Project Structure

### Documentation (this feature)

```text
specs/006-mentor-transfusion/
├── plan.md              # This file
├── research.md          # Phase 0 (assessment + R1–R6)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── mentor-math.md
│   ├── transfer-mentor-xp-rpc.md
│   └── development-mentor-ui.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/
├── mentor_math.py           # NEW — conversion, eligibility, headroom, max units
├── progression.py           # REUSE — simulate_apply_card_xp, L_MAX, cumulative_xp_for_level
├── progression_gates.py     # REUSE — optional UI hints; mentor eligibility is mentor_math
└── __init__.py              # MODIFY — export mentor helpers/constants

apps/discord_bot/
├── cogs/development_cog.py  # MODIFY — maxed Allocate Skills → mentor flow
├── cogs/player_cog.py       # MODIFY — Mentor Ready SP field copy
├── core/api_errors.py       # MODIFY — mentor RPC error strings
└── (optional) embeds/mentor_embeds.py  # ONLY if development_cog gets too large

supabase/migrations/
└── 052_mentor_transfusion.sql   # NEW — table, RLS, RPC, schema guard

supabase/scripts/verify_required_schema.sql  # EXTEND — table + function (+ policies)

tests/
└── test_mentor_math.py      # NEW — conversion, eligibility, headroom, max units

scratch/apply_migration_052.py   # NEW — apply pattern
change_log.md                    # MODIFY on ship
AGENTS.md / .agents/AGENTS.md    # MODIFY on ship — mentor pipe note
.specify/specs/v1.0.0/spec.md + plan.md  # RECONCILE on implement
```

**Structure Decision**: Keep conversion math in `player_engine` (stateless). Persist and mutate only through `transfer_mentor_xp`. Discord stays a thin deferred UI over that RPC, mirroring fusion under `/development`.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Notes (for `/speckit.tasks`)

1. **Constants** — `SP_PER_MENTOR_UNIT=5`, `XP_PER_MENTOR_UNIT=500`, `MENTOR_TRANSFERS_DAILY_LIMIT=3`; mirror in SQL RPC body.
2. **RPC order** — lock source+target → validate ownership/eligibility/SP/daily count/XP headroom → debit SP (spent +=) → `apply_card_xp(target, 500*N, 'mentor_transfer')` → INSERT log → return JSON preview fields.
3. **XP headroom** — reject if `xp_wasted` would be &gt; 0; UI Max uses `mentor_max_units(source_sp, target_xp)`.
4. **UI** — short-lived views (not persistent `custom_id` registration) unless fusion pattern already requires otherwise; always `defer` first.
5. **Env kill-switch (optional)** — `MENTOR_TRANSFUSION_ENABLED` default true; when false, hide mentor UI only.
6. **Out of scope** — match engine, economy, marketplace prices, new slash commands, automatic mentor suggestions, profile Mentor button.

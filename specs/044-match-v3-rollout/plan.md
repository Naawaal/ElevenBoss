# Implementation Plan: Match Engine V3 Production Rollout

**Branch**: `044-match-v3-rollout` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/044-match-v3-rollout/spec.md`

**US citation**: Extends Implemented `041`; mutating settlement paths remain under **US-42.4 Match Integrity**. No marketplace scope.

## Summary

Safely **turn on** Match Engine V3 (already implemented under `041`, flags default off) in cutover order **bot → league → (optional) friendly**, and make post-match **explainability** manager-readable when V3 runs. Prefer **no new migration** and **no new slash command** — ops flips existing `game_config` keys; Discord reuses existing finalize embeds; enrich the Phase-0 `project_explanation` stub so Decision Windows / key moments read as football, not raw event types.

**Technical approach**: (1) Verify kickoff pin via `resolve_engine_version` on all create-run paths. (2) Enrich `packages/match_engine/match_engine/v3/projectors.py` + unit tests. (3) Polish Discord “How it was decided” copy in `battle_cog.py` finalize handlers (bot + league, including auto-sim). (4) Document soak gate + rollback in quickstart; flip flags in staging then prod; update `change_log.md` when bot (then league) goes live for players.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase) — existing stack

**Primary Dependencies**: Existing `match_engine` v3, `battle_cog` / league play / auto-sim, `game_config` flags from migration `083`, settle-once RPCs unchanged

**Storage**: **No new tables expected.** Uses `match_runs.engine_version`, `match_events`, `game_config` keys already from `083`

**Testing**: Extend projector unit tests; re-run `041` V3 suite; Discord/ops soak checklist in quickstart

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo rollout (packages + discord_bot; ops config)

**Performance Goals**: No hub-path work; silent sim budget unchanged from `041`; explainability projection O(events) once per match end

**Constraints**: Constitution / AGENTS — no Discord in packages; no parallel XP/coin pipes; no new slash command; YAGNI — no Redis, marketplace, wages flip; kickoff pin immutable; US-42.4 settle-once

**Scale/Scope**: ~1 package projector touch; Discord copy polish; ops docs + flag flips; optional tiny helper for readable tip text

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Projector enrichment in `packages/match_engine`; Discord only formats/displays |
| II. DB via RPC | PASS | No new money mutations; flags via existing `game_config` |
| III. Typing / Pydantic | PASS | Keep `Explanation` model; typed tip dicts |
| IV. Slash + defer | PASS | No new slash command; existing `/battle` / league flows |
| V. APScheduler | PASS | Auto-sim already calls league path; honors league flag at run create |
| VI. Friendly errors | PASS | Explainability failure must not block settlement (already settlement-first) |
| VII. YAGNI | PASS | No engine rewrite; no new tables; enrich stub + ops rollout |

**Post-Phase 1 re-check**: PASS — contracts document flag order, pin, explainability display, soak gate; data model confirms reuse of `083` schema.

## Project Structure

### Documentation (this feature)

```text
specs/044-match-v3-rollout/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── engine-flag-rollout.md
│   ├── explainability-ui.md
│   └── soak-and-rollback.md
└── tasks.md                # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
packages/match_engine/match_engine/v3/projectors.py   # enrich project_explanation
packages/match_engine/match_engine/v3/__init__.py     # exports if needed
tests/test_nss_v3_projectors.py                      # extend explainability cases

apps/discord_bot/cogs/battle_cog.py                  # readable tip lines in finalize embeds
apps/discord_bot/core/match_runs.py                  # verify-only unless bug found

change_log.md                                        # when bot/league flags go live for players

# Ops (no code required if SQL/dashboard used):
# UPDATE game_config SET value_json='1' WHERE key='match_engine_v3_bot';
```

**Structure Decision**: Extend existing V3 + battle finalize paths; do not add apps/packages. Agent-context update script absent — skipped.

## Complexity Tracking

> No constitution violations.

| Choice | Why | Simpler alternative rejected |
|--------|-----|------------------------------|
| Enrich projector (not only ops flag flip) | Spec US2 requires readable explainability; Phase-0 stub shows raw `GOAL` type | Flag-only rollout leaves “How it was decided” thin |
| No new migration | `083` already has flags + `engine_version` + events | Ops metrics table YAGNI |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research + decisions | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Frozen implementation decisions

| ID | Decision |
|----|----------|
| D1 | Rollout only — no engine rewrite |
| D2 | Cutover order: bot → league → optional friendly |
| D3 | Existing `game_config` keys; defaults stay `0` until ops flip |
| D4 | Kickoff pin via `resolve_engine_version` / create-run — immutable |
| D5 | Explainability from `project_explanation`; Discord formats tips; never invent events |
| D6 | Enrich projector beyond GOAL/CHANCE to include Decision Window / high-signal tactical moments when present in stream |
| D7 | Settlement always before / independent of explainability presentation |
| D8 | No new migration unless a bug forces a forward fix |
| D9 | Soak gate documented before league enable (see soak contract) |
| D10 | Non-goals: marketplace, wages, Redis, Ranked, squad Tactics Soon |

## Next command

`/speckit.tasks` — break this plan into implementation tasks.

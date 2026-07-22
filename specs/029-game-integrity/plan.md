# Implementation Plan: Game Integrity & State Management (US-42 Epic)

**Branch**: `029-game-integrity` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Status**: Locked (2026-07-22) — epic governance complete; children Implemented under `030`–`035`

**Input**: Feature specification from `/specs/029-game-integrity/spec.md`

**Plan type**: **Epic governance & delivery plan** — not a single-feature code wave. Production mutations ship only under child features US-42.1–US-42.10 after each child’s own `/speckit.specify` → `/speckit.plan` → `/speckit.tasks`.

## Summary

Operationalize the US-42 integrity constitution: freeze principles/invariants as the review gate for all future mutations, sequence ten child Speckit features, and define shared contracts (invariant checklist, child template, SoT conflict resolution) so identity, state machines, match/league/market/economy integrity, scheduler, RPC guarantees, and anti-abuse catalogs can be specified and implemented incrementally without forking pipes or inventing parallel economies.

**Technical approach**: Documentation-first in `specs/029-game-integrity/`. Adopt epic into SDD pointers (`AGENTS.md`, optional v1.0.0 stub). No new slash commands, hubs, or tables from this folder. Child waves may add migrations/RPCs/package helpers only when their Locked plans require them — always via single XP/economy pipes and monorepo boundaries.

## Technical Context

**Language/Version**: Python 3.11+ (CPython) / Postgres 15+ (Supabase) — locked by constitution

**Primary Dependencies**: Existing stack — discord.py, supabase async, pydantic, APScheduler; packages `economy`, `player_engine`, `match_engine`, `leagues`, `gacha`, `energy`

**Storage**: Existing Supabase schema/RPCs (`apply_club_economy`, `apply_card_xp`, `match_locks`, `economy_ledger`, league/transfer tables). **No schema change authorized by this epic plan.** Children propose forward migrations only with US-42.9 compliance.

**Testing**: Epic validates via process + doc gates (see [quickstart.md](./quickstart.md)). Child plans own pytest/race/smoke suites. Existing suites (`tests/test_transfer_market_race.py`, economy/match parity) remain regression anchors.

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase; future clients must reuse mutation contracts

**Project Type**: Monorepo **epic program** — docs + process; code only in descendant feature folders

**Performance Goals**: N/A for epic docs. Child plans must keep mutations inside existing RPC transactions; no new N+1 grant loops

**Constraints**: Constitution + AGENTS.md — no `discord` in `packages/`; single coin/XP pipes; no new player surfaces from epic; YAGNI; child implementations must cite US-42 + child ID; fail closed on degraded dependencies; presentation ≠ settlement

**Scale/Scope**: 1 epic folder + 10 child Speckit features; P0 children first (42.1–42.4, 42.7, 42.9); overlays 42.5/42.6 on `026`/`017`; 42.8/42.10 close the loop

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Epic ships no packages; children may add pure state/gate helpers only |
| II. DB mutations via RPC / atomic paths | PASS | Epic forbids new cog-level multi-step money/XP writes; elevates pipe invariants |
| III. Typing / Pydantic at boundaries | PASS | Future child helpers use Pydantic at package boundaries |
| IV. Slash + defer | PASS | No new slash commands from epic |
| V. APScheduler | PASS | US-42.8 will require thin wake-ups + catch-up; no competitive rules in cron bodies |
| VI. User-friendly errors | PASS | FR-013 — integrity failures → clear ephemeral families |
| VII. YAGNI | PASS | Epic is constitution + sequencing; no speculative ban systems or multi-club |

**Post-Phase 1 re-check**: PASS — artifacts are contracts/templates/entity maps only; Complexity Tracking empty; no unjustified new packages or surface area.

## Project Structure

### Documentation (this feature)

```text
specs/029-game-integrity/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1 — conceptual integrity entities
├── quickstart.md           # Phase 1 — epic adoption & child kickoff validation
├── contracts/
│   ├── invariant-checklist.md
│   ├── child-spec-template.md
│   ├── source-of-truth-and-amendments.md
│   └── delivery-waves.md
├── checklists/requirements.md
└── tasks.md                # /speckit.tasks — NOT created by /speckit.plan
```

### Source Code (repository root)

```text
# Epic adopts into existing trees — no new runtime modules required for 029 itself.

AGENTS.md                              # pointer: cite US-42 for integrity mutations (tasks)
.specify/specs/v1.0.0/spec.md          # optional US-42 stub pointer (tasks)
.specify/memory/constitution.md        # platform constitution — complementary, not replaced

# Child waves (future feature folders — illustrative numbering):
# specs/030-identity-ownership/     → US-42.1
# specs/031-player-state-machine/   → US-42.2
# … through US-42.10

# When children implement, expected touch zones (not authorized by this plan alone):
packages/player_engine/                # pure gates / state enums
packages/economy/                      # faucet/sink registry mirrors
packages/leagues/                      # integrity overlays only
apps/discord_bot/core/                 # RPC wrappers, locks, recovery
apps/discord_bot/cogs/                 # revalidation only — no new hubs from epic
supabase/migrations/NNN_*.sql          # child-owned forward migrations
tests/                                 # race / idempotency / state-matrix tests
```

**Structure Decision**: Keep US-42 epic artifacts under `specs/029-game-integrity/`. Do **not** create a new Python package for “integrity.” Shared pure helpers land in existing packages when a child plan needs them. Runtime enforcement stays in RPCs + thin app adapters.

## Complexity Tracking

> No constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Delivery Phases (epic program)

| Phase | Work | Exit gate |
|-------|------|-----------|
| **E0** | Lock epic spec + this plan + contracts | Checklist green; team can cite INV-IDs |
| **E1** | Specify children P0: 42.1 → 42.2 → 42.3 (serial preferred) | Each child `spec.md` Locked |
| **E2** | Specify 42.4 + 42.7 + draft 42.9 template obligations | Match + economy integrity specs Locked |
| **E3** | Specify 42.5 / 42.6 overlays; 42.8; finalize 42.9 / 42.10 | All ten children specified |
| **E4** | Per-child plan → tasks → implement in dependency order | SC-002/003-style suites green per child |
| **E5** | Adoption: reviews require US-42 citation; changelog when player-visible | SC-005 process metric |

**Hard rule**: `/speckit.tasks` on `029` may only produce **documentation/process tasks** (pointers, templates, child kickoffs) — never a migration that implements all domains at once.

## Key Design Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Decisions: epic-vs-impl, child order, overlay vs rewrite, soft anti-abuse |
| [data-model.md](./data-model.md) | Conceptual entities (Logical Action, Exclusive State, registries) — not new tables |
| [contracts/invariant-checklist.md](./contracts/invariant-checklist.md) | PR/review gate for mutations |
| [contracts/child-spec-template.md](./contracts/child-spec-template.md) | Required sections for US-42.x specs |
| [contracts/source-of-truth-and-amendments.md](./contracts/source-of-truth-and-amendments.md) | Conflict resolution + amendment process |
| [contracts/delivery-waves.md](./contracts/delivery-waves.md) | Sequencing & parallelization rules |
| [quickstart.md](./quickstart.md) | Validate epic readiness and start US-42.1 |

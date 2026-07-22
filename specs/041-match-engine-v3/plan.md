# Implementation Plan: Match Engine V3 — Deterministic Tactical Engine

**Branch**: `041-match-engine-v3` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/041-match-engine-v3/spec.md`

**Overlays**: NSS v2 production (`packages/match_engine`), US-42.4 (`033-match-integrity`), injury/fatigue (`002`/`016`), live immersion (`004`), league lifecycle (`026`), US-23/US-25 pipes

**Status**: Implementation complete (T001–T079). Prod/staging flags remain **off**; next step is bot-flag soak.

---

## Summary

Evolve ElevenBoss from **NSS v2** (Discord-coupled async Markov stream) into **NSS v3**: a **deterministic, step-based, event-sourced tactical simulation core** in `packages/match_engine`, with Discord as a pure event consumer. Phase 0 preserves today’s match feel and integrity guarantees while introducing `step()`, immutable `MatchContext`, decision events, and durable ordered events for replay/recovery. Later waves add transition-based tactics, replay-safe touchline, explainability projections, and a decoupled `BotBrain` — without merging Dixon-Coles into live play.

**Technical approach**:
1. **Extract Simulation Core** — wrap/refactor `v2_simulator` into pure `SimulationEngine.step(context, decision_queue) → StepResult`; Discord/`collect_match_events` become adapters.
2. **Event SoT** — every sporting/decision occurrence is a versioned `MatchEvent`; stats/commentary/explainability are projectors.
3. **Durable events** — append-only `match_events` table keyed by `run_id` + `seq` (bot/league); friendlies ephemeral-or-short-TTL (research R2).
4. **Engine version pin** — `match_runs.engine_version` (`nss_v2` | `nss_v3`) so in-flight runs never cross engines.
5. **Dual-run** — feature flag / percent rollout by match type; settlement pipes unchanged.
6. **Dixon-Coles** — offline calibration/regression harness only (research R7).

Architecture pack (spec Planning Deliverables Gate):

| # | Deliverable | Artifact |
|---|-------------|----------|
| 1 | Current architecture review | [contracts/architecture-review.md](./contracts/architecture-review.md) |
| 2 | Gap analysis v2→v3 | same + [research.md](./research.md) |
| 3 | Domain model | [data-model.md](./data-model.md) |
| 4 | Event model | [contracts/event-model.md](./contracts/event-model.md) |
| 5 | Database design | [contracts/event-store.md](./contracts/event-store.md) |
| 6 | API design | [contracts/simulation-api.md](./contracts/simulation-api.md), [contracts/ai-decision.md](./contracts/ai-decision.md), [contracts/commentary-projection.md](./contracts/commentary-projection.md) |
| 7 | Migration strategy | [contracts/migration-dual-run.md](./contracts/migration-dual-run.md) |
| 8 | Testing strategy | [quickstart.md](./quickstart.md) + plan §Testing |
| 9 | Risk analysis | [contracts/risk-and-performance.md](./contracts/risk-and-performance.md) |
| 10 | Performance analysis | same |

---

## Technical Context

**Language/Version**: Python 3.11+ / PostgreSQL 15+ (Supabase)

**Primary Dependencies**: `pydantic>=2`, existing `match_engine` / `player_engine` / `economy` packages; Discord bot adapters in `apps/discord_bot/`; no new runtime deps for Phase 0

**Storage**: Extend `match_runs` (`engine_version`, optional `event_schema_version`, decision log pointer); new `match_events` (append-only); existing settlement RPCs untouched in ownership

**Testing**: Pytest — deterministic hash replay, win-rate gates (`test_nss_win_rates` / `benchmark_nss`), recovery parity, projector tests, dual-run matrix, fuzz seeds; optional offline Dixon-Coles calibration scripts under `scripts/` / `scratch/` (not production path)

**Target Platform**: Discord bot on Render + hosted Supabase; silent auto-sim in-process

**Project Type**: Pure package core + Discord adapters + one forward migration

**Performance Goals**: Silent full match **&lt; 50 ms CPU** on CI reference (SC-004); live path latency dominated by Discord sleeps (unchanged); event insert batching ≤1 round-trip per checkpoint (see event-store)

**Constraints**:
- Constitution I–VII (no Discord/DB in `packages/`; async Supabase RPCs for mutations; Pydantic boundaries; YAGNI)
- US-42.4 settle-once / locks / friendly sandbox
- Single XP/coin pipes; no parallel settlement
- Determinism: no `time`, no global `random`, no unordered dict iteration affecting RNG draws
- Phase 0 before player-facing tactic overhaul (FR-018)

**Scale/Scope**: ~80–200 events/match; thousands of matches/day at mid scale; event table growth managed by retention policy; dual-run for weeks then pin v3

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Sim/AI/projectors in `packages/match_engine`; Discord only consumes events |
| II. DB via RPC/atomic | PASS | Event append via batched insert or thin RPC; rewards stay existing RPCs |
| III. Typing / Pydantic | PASS | `MatchContext`, `MatchEvent`, `StepResult` as models |
| IV. Slash + defer | PASS | No required new slash command; extend `/battle` touchline/views only |
| V. APScheduler | PASS | League auto-sim continues via existing schedulers calling silent adapter |
| VI. Errors / observability | PASS | Domain errors; recovery classification unchanged in intent |
| VII. YAGNI | PASS | Phase 0 = extract+events+pin; tactics/AI after acceptance — see Complexity |

**Post-Phase 1 re-check**: PASS — contracts keep packages pure; event table + RLS; Dixon-Coles not wired to Discord; no second economy/XP pipe.

---

## Project Structure

### Documentation (this feature)

```text
specs/041-match-engine-v3/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
├── contracts/
│   ├── architecture-review.md
│   ├── event-model.md
│   ├── event-store.md
│   ├── simulation-api.md
│   ├── ai-decision.md
│   ├── commentary-projection.md
│   ├── migration-dual-run.md
│   └── risk-and-performance.md
└── tasks.md                    # /speckit.tasks — NOT this command
```

### Source Code (repository root)

```text
packages/match_engine/
├── match_engine/
│   ├── v2_simulator.py          # keep during dual-run; thin-wrap or deprecate after cutover
│   ├── v3/
│   │   ├── __init__.py
│   │   ├── context.py           # MatchContext (immutable), DecisionContext
│   │   ├── engine.py            # SimulationEngine.step / run_to_completion
│   │   ├── phases.py            # Markov transitions (ported from v2)
│   │   ├── events.py            # MatchEvent types + schema_version
│   │   ├── projectors.py        # box score, MOTM hints, explainability
│   │   ├── decisions.py         # validate/apply DecisionIntent
│   │   ├── tactics.py           # Phase 0: map Attack/Balanced/Defend; Phase 1+: styles
│   │   └── rng.py               # seeded Random factory — no globals
│   ├── bot_squad.py             # unchanged
│   ├── commentary_engine.py     # consume projected commentary vars from events
│   └── ...
├── match_engine.py              # Dixon-Coles interval — calibration only (scripts)
└── __init__.py                  # facade: export v3 API + legacy aliases

packages/player_engine/          # injury/fatigue formulas — called from v3 injury events (pure)

apps/discord_bot/
├── cogs/battle_cog.py           # adapter: step loop + sleep; no sporting mutation
├── core/match_runs.py           # engine_version pin; event flush helpers
├── core/match_events_store.py   # NEW: append/list events for run
├── core/match_recovery.py       # replay via v3 run_to_completion + decision log
└── views/                       # touchline → DecisionIntent queue (post–Phase 0 rules)

supabase/migrations/
└── NNN_match_engine_v3_events.sql   # match_events + match_runs columns + RLS + guards

scripts/                         # optional: calibrate_dixon_coles.py, compare_v2_v3_seeds.py
tests/
├── test_nss_v3_determinism.py
├── test_nss_v3_projectors.py
├── test_nss_v3_recovery_parity.py
├── test_nss_v3_dual_run_pin.py
└── (extend) test_nss_win_rates.py / test_match_integrity_*
```

**Structure Decision**: New `packages/match_engine/match_engine/v3/` package subtree keeps v2 importable during dual-run. Discord never imports Dixon-Coles. DB IO stays in `apps/discord_bot/core/`.

---

## Complexity Tracking

| Violation / Extra surface | Why Needed | Simpler Alternative Rejected Because |
|---------------------------|------------|--------------------------------------|
| New `match_events` table | Durable ordered SoT for replay/analytics | JSON array on `match_runs` — poor concurrency, rewrite amplification, weak indexing (research R2) |
| `v3/` subtree alongside v2 | Dual-run without big-bang rewrite | In-place mutate v2 only — cannot pin in-flight runs or A/B safely |
| DecisionInbox + Wave 1 windows | Replay-safe human input without Phase 0 feel drift | Keep free mutation of `MatchState` — breaks determinism on recovery |
| Offline Dixon-Coles harness | Balance without live merge | Merge into live path — violates FR-015 and dual-truth risk |

---

## Implementation Waves

### Wave 0 — Phase 0 Simulation Core (architectural parity)

- Port Markov loop to `SimulationEngine.step` + `run_to_completion`
- Immutable `MatchContext`; Possession aggregate; possession-boundary event flush
- Event categories + three digests (Sporting / Deterministic Replay / Settlement)
- `DecisionInbox` + window **metadata**; **immediate** apply (v2 parity)
- Thin `BotBrain → Policy` (DefaultPolicy only); Replay projector stub
- `packages/match_engine/contracts/` + `calibration/`; Golden Corpus 50–100
- `match_events` + `engine_version` + `simulation_schema_version` pin
- Adapters: battle live loop, silent collect, recovery
- **Exit**: SC-001/002/003/004/007/008/009/010/011; FR-018 unlocks Wave 1 — **no intentional gameplay change**

### Wave 1 — DecisionWindow enforcement + explainability

- Fixed DecisionWindows (15/30/45/60/75/85) become authoritative apply points
- Bump `simulation_schema_version`; regenerate Golden Corpus; player-facing changelog
- Richer post-match explainability UI (projector → embeds)
- Recovery uses schema-pinned decision apply semantics

### Wave 2 — Tactical styles (P2 story 6)

- Transition profiles: Possession, Counter, Long Ball, High Press (+ Balanced)
- Schema bump; distinguishability tests (SC-005); win-rate band re-approval if shifted

### Wave 3 — Richer policies (P3 story 8)

- Additional Policy implementations behind BotBrain (not Adaptive ML)
- Personality/difficulty hooks documented; DefaultPolicy remains Phase 0 baseline

---

## Testing Strategy (Deliverable 8)

| Class | What | Gate |
|-------|------|------|
| Deterministic replay | Same seed+squads+decisions → identical event hash | SC-001 |
| Property | Event seq monotonic; score equals GOAL count; FT ends stream | always |
| Probability regression | Existing win-rate / possession integrity suite on v3 Balanced | SC-008 |
| Performance | Silent full match CPU budget | SC-004 |
| Concurrency | Double settle / dual finalize with events present | US-42.4 |
| Recovery | Crash mid-stream → complete matches clean replay | SC-002 |
| Migration | Run pinned v2 finishes v2; new runs v3 under flag | dual-run contract |
| Fuzz | Random seeds + random legal decision schedules | no crash; determinism holds |
| Projector | Stats from events == prior live counters on golden streams | FR-004 |
| Tactic distinguishability | Histogram classifier Possession vs Counter | SC-005 (Wave 2) |

---

## Risk Summary (Deliverable 9 — detail in contract)

Highest risks: **feel drift** during Phase 0 port; **touchline desync** if decisions not evented; **event table write amplification**; **dual-run mis-pin**; **projector/reward field mismatch** (scorer names). Mitigations: golden seed corpus, version pin, batched appends, settle-once unchanged, contract tests on GOAL fields.

---

## Performance Summary (Deliverable 10 — detail in contract)

Per match ~100–200 events × ~200–400 B ≈ **&lt; 100 KB**. CPU dominated by RNG + phase math (already sub-10 ms typical). DB: batch insert every N events or on checkpoint/HT/FT — not one RPC per event on live path. Indexes: `(run_id, seq)` unique. Retention: competitive long; friendly short/none durable.

---

## Next Command

Wave 1 (DecisionWindows) + Wave 2 (TransitionProfiles) + Wave 3 policy modules are implemented (`simulation_schema_version=2`).

**Still gated**: prod/staging flag enable for `match_engine_v3_*`. Soak bot flag first.

Optional later: richer explain UI, player-traits, Adaptive AI beyond Aggressive/Defensive policies.

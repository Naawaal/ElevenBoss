# Data Model: Match Engine V3

**Feature**: `041-match-engine-v3`  
**Date**: 2026-07-22

Pure-domain types live in `packages/match_engine`. Durable rows live in Postgres (see [contracts/event-store.md](./contracts/event-store.md)).

---

## Aggregates

### MatchRun (durable aggregate root — app/DB)

Identity for one simulation instance.

| Field | Notes |
|-------|--------|
| id | UUID |
| run_type | `bot` \| `friendly` \| `league` |
| status | `streaming` \| `completing` \| `completed` \| `abandoned` \| `failed` |
| sim_seed | int64 — sole sporting RNG seed |
| engine_version | `nss_v2` \| `nss_v3` — **pin** |
| event_schema_version | int — for projectors |
| squad_snapshot | JSON — kickoff XIs + benches + ratings |
| decision_log_digest | optional hash for integrity checks |
| scores / last_minute | mirrors for recovery UX |
| fixture_id / discord ids / thread ids | existing |

**Invariants**: status transitions per US-42.4; engine_version immutable after insert; sim_seed immutable.

---

### SimulationSession (in-process aggregate)

Not stored as one blob. Composed of:

- `MatchContext` (current immutable snapshot)
- `DecisionInbox` (pending intents)
- `RngState` (derived from seed + draw count; or re-seeded Random advanced only via engine)
- Accumulated `MatchEvent` buffer since last flush

---

## Entities

### MatchPlayer (value within context)

Card snapshot for sim: id, name, position, overall, pac/sho/pas/dri/def/phy, fatigue, morale, playstyles, compromised, emergency_gk, age (injury).

### MatchEvent (entity in stream)

See [contracts/event-model.md](./contracts/event-model.md). Ordered by `seq` within `run_id`.

### DecisionIntent (command → becomes event if accepted)

| Field | Notes |
|-------|--------|
| side | home \| away |
| kind | `set_tactic` \| `sub_resolution` \| `play_on` \| … |
| payload | style id, replacement card id, etc. |
| requested_at_minute | match clock when UI queued |
| source | `human` \| `ai` \| `auto` |

---

## Value Objects

### MatchContext (immutable per step)

| Field | Notes |
|-------|--------|
| minute | 0–90 |
| home_score / away_score | |
| phase | Markov phase enum |
| attacking_side | home \| away |
| momentum_home / momentum_away | internal ±10 |
| stagnation_home / away | |
| tactic_home / tactic_away | style ids |
| stance_modifier_home / away | float (compat with 1.3/1.0/0.7) |
| squad_home / squad_away | player snapshots |
| bench_home / bench_away | |
| subs_used_* / injury_used_* | |
| intensity_tier | |
| injuries_enabled / interactive_sides | |
| schema_version / engine_version | |
| rng_draw_count | for replay diagnostics |
| awaiting_decision | bool + reason |

**Weather**: optional nullable field reserved; unused in Phase 0 (Assumption).

### DecisionContext (read-only)

Derived: phase, possession side, score, minute, legal_actions[], last_N event summaries, fatigue pressure hints. Never includes writable squad references that AI can mutate in place (pass copies/snapshots).

### TransitionProfile

Named style → clock multipliers, transition weights, press rates, fatigue pressure. Phase 0: three stance profiles; Wave 2: five styles.

### StepResult

`events`, `context`, `elapsed_minutes`, `terminal`, `awaiting_decision`, `replay_meta`.

### BoxScoreProjection / ExplanationProjection

Derived only from events (+ optional kickoff snapshot for names).

---

## State Transitions

### MatchRun.status

```text
streaming → completing → completed
streaming → abandoned | failed
completing → completed | failed
```

Unchanged from US-42.4 intent.

### Simulation phase (sporting)

Unchanged Markov graph from NSS v2 (MIDFIELD, BUILD_UP, ATTACK, SCORING_OPP, SET_PIECE, COUNTER_ATTACK) with HT/FT terminals. Wave 2 adjusts **weights/timings**, not the graph topology (unless a researched extension adds an explicit PRESS phase later — out of Phase 0).

### Decision barriers

Pending intents apply only at barriers (research R4); emit `TACTICAL_DECISION` or resolution events; update context tactics fields.

---

## Relationships

```text
MatchRun 1 ── * MatchEvent
MatchRun 1 ── 1 squad_snapshot (kickoff)
MatchRun 1 ── * DecisionIntent (accepted subset ⊂ events)
MatchEvent * ── projects → BoxScore, Explanation, CommentaryVars
BotBrain / HumanUI → DecisionIntent → SimulationEngine
```

---

## Validation Rules

- `seq` strictly increasing per run starting at 1
- Exactly one `KICKOFF`; exactly one `FULL_TIME` on completed sims
- GOAL increments score by 1 for scoring side in projection
- At most one injury resolution chain per side per match (existing rule)
- Tactic change cooldown in match-minutes (defaults M=5)
- Friendly runs must not call reward RPCs (app-level; unchanged)
- `engine_version` required on insert for new code paths

---

## Persistence Mapping

| Domain | Storage |
|--------|---------|
| MatchRun | `match_runs` |
| MatchEvent | `match_events` (bot/league) |
| Kickoff snapshot | `match_runs.squad_snapshot` |
| Friendly summary | `friendly_match_logs` (existing) |
| Settlement | `match_history` + RPCs (unchanged ownership) |

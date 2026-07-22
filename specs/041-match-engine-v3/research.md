# Research: Match Engine V3

**Feature**: `041-match-engine-v3`  
**Date**: 2026-07-22  
**Status**: All planning unknowns resolved (no remaining NEEDS CLARIFICATION for Phase 0)

---

## R1 — Simulation API shape: step-based engine

**Decision**: Introduce `SimulationEngine.step(context: MatchContext, inbox: DecisionInbox) -> StepResult` where `StepResult` contains `events: list[MatchEvent]`, `context: MatchContext` (new immutable snapshot), `elapsed_minutes: int`, `terminal: bool`, and `replay_meta` (schema version, engine version, rng_draw_count). Provide `run_to_completion(...)` as a loop over `step` for silent/auto-sim/recovery/tests.

**Rationale**: Spec FR-003 requires Discord-independent progression. Step boundaries align with phase transitions and decision application points, making replay and injury pauses explicit.

**Alternatives considered**:
- Keep only `async for` generator — rejected (harder to unit-test mid-state; Discord still owns control flow).
- Full ECS tick-per-second — rejected (YAGNI; overkill vs Markov phases; changes feel).
- Transactional “simulate entire match” RPC in Postgres — rejected (constitution: pure logic in packages; SQL cannot own Discord pause UX).

---

## R2 — Event store: append-only `match_events` table vs JSON on `match_runs`

### Comparison

| Concern | JSONB array on `match_runs` | Append-only `match_events` rows |
|---------|------------------------------|----------------------------------|
| Concurrency | Row rewrite races; need advisory lock / full replace | Insert-only; natural append under `run_id` |
| Replay | Load whole blob | `ORDER BY seq` stream / window |
| Indexing | Weak (JSONB path indexes costly) | Strong: `(run_id, seq)`, type, minute |
| Performance | Rewrite grows O(n²) with updates | O(1) append; batch COPY/insert |
| Recovery | Easy to load one row; easy to corrupt mid-write | Resume from `max(seq)`; partial append visible |
| WAL / storage | Large TOAST updates amplify WAL | Many small inserts; batching reduces chatter |
| Analytics | Painful | SQL aggregates by type/tactic |
| Complexity | Simpler schema | Extra table + RLS + retention |

**Decision**: **Append-only `match_events`** for **bot** and **league** runs. Live path buffers events in memory and **flushes in batches** (checkpoint every N events and always at HT/FT/injury pause/complete). **Friendly**: default **no durable event rows** (in-memory + existing `friendly_match_logs` summary); optional short-TTL later if recovery needs it — recovery today can re-sim from seed+snapshot without full event log if no mid-match decisions, or store decision log only.

**Rationale**: Matches FR-006, analytics, and concurrency under Render multi-instance risk; avoids JSON rewrite amplification. Friendlies stay cheap (sandbox).

**Alternatives considered**:
- JSONB-only — rejected for competitive scale and concurrent recovery.
- External object store (S3) for streams — rejected (ops complexity; YAGNI at current scale).
- Event sourcing bus (Kafka) — rejected (overkill).

---

## R3 — Immutability model

**Decision**: `MatchContext` is a Pydantic model treated as **immutable per step** (engine returns a new instance or validated copy). Internal engine may use private mutable builders **inside a single step** then freeze. `DecisionContext` is a derived read-only view (`from_context(ctx, legal_actions)`). AI/UI never receive mutable engine internals.

**Rationale**: Spec Phase 0 requirements; prevents accidental Discord-side mutation during sleep gaps.

**Alternatives considered**: Fully persistent structural sharing (pyrsistent) — rejected (dependency + unfamiliar); frozen dataclasses only — Pydantic already project standard (constitution III).

---

## R4 — Human decisions: Inbox now; fixed windows in Wave 1

**Decision**:
1. Touchline UI queues intents into **DecisionInbox** (validate → collapse → apply).
2. **Phase 0**: apply semantics remain **immediate** (NSS v2 parity); Decision events persist with window metadata; replay/recovery consume those events.
3. **Wave 1**: fixed DecisionWindows at **15' / 30' / 45' / 60' / 75' / 85'** become authoritative; bump `simulation_schema_version`; regenerate Golden Corpus; player-facing changelog.
4. `simulation_schema_version` defines **gameplay semantics**, not only data shapes.
5. Decisions after `FULL_TIME` are ignored.

**Rationale**: Clarification Session 2026-07-22 Q4 — architectural scaffolding without Phase 0 gameplay drift.

**Alternatives considered**:
- Enforce fixed windows in Phase 0 — rejected (changes touchline timing vs v2).
- Disable touchline in Phase 0 — rejected (worse UX; unnecessary if immediate apply preserved).
- Wall-clock cooldown — rejected (non-deterministic across recovery).

---

## R5 — Tactical styles: transition profiles, not goal% padding

**Decision**: Represent each style as a **TransitionProfile**:
- multipliers on phase clock ranges (build-up length)
- weights for MIDFIELD→BUILD_UP vs SET_PIECE / COUNTER paths
- stagnation sensitivity
- press/turnover event emission rates
- fatigue pressure multiplier fed into injury/fatigue stance mapping
- **Do not** primarily add flat bonuses to SCORING_OPP goal chance; goal rate may change **indirectly** via more/fewer shots and better/worse chance quality

Phase 0 maps existing Attack/Balanced/Defend to stance multipliers compatible with today’s `home_tactics_modifier` (1.3/1.0/0.7) for parity. Wave 2 adds Possession / Counter / Long Ball / High Press profiles.

**Rationale**: Spec FR-011 / User Story 6; explainability (“they sat deep and countered”) beats “+8% RNG”.

**Alternatives considered**:
- Five interval-engine tactic presets verbatim — useful inspiration; not copy-paste (different phase model).
- Only commentary flavor text — rejected (no gameplay).
- Inflate goal base by style — rejected by master prompt.

---

## R6 — AI architecture: BotBrain as event producer

**Decision**: `BotBrain.propose(decision_context) -> DecisionIntent | None`. Simulation applies intents through the same `decisions.apply` path as humans. Default brain: static Balanced (or division-calibrated stance) matching today’s non-interactive away side. Personalities/difficulty = alternate brains later.

**Rationale**: FR-013; prevents AI from calling `state.home_score += 1`.

**Alternatives considered**: AI mutates `MatchTeamState` — rejected. Shared neural net service — out of scope.

---

## R7 — Dixon-Coles role

**Decision**: **Calibration / Monte Carlo / regression only**. Harness in `scripts/` compares distribution of v3 scores vs Dixon-Coles expectations for OVR gaps; may suggest TransitionProfile tweaks. **Never** called from `battle_cog` or settlement.

**Rationale**: FR-015; avoids dual scoring truths and Discord coupling to interval engine complexity.

**Alternatives considered**: Hybrid live (DC scores + NSS commentary) — deferred indefinitely; changelog already estimated 1–2 weeks and integrity risk is high. Delete interval engine — rejected (still valuable as offline tool).

---

## R8 — Dual-run / migration

**Decision**:
1. Add/use `match_runs.engine_version` text (`nss_v2` | `nss_v3`) set at `create_*_run`.
2. Feature flag `match_engine_v3` in `game_config` (or env) with optional per-`run_type` keys.
3. In-flight v2 runs always recover/complete on v2 code paths.
4. Cutover order: **bot → league auto-sim → league live → friendly** (friendly last; least integrity risk but also least need for events).
5. Rollback: flip flag off; new runs v2; do not rewrite historical v3 events.

**Rationale**: FR-009; Render restarts mid-match are routine.

**Alternatives considered**: Big-bang cutover — rejected. Percent hash(discord_id) — optional later; start with boolean flag per type.

---

## R9 — Statistics / commentary projection

**Decision**: `project_box_score(events) -> MatchLiveStats-equivalent`; `project_explainability(events) -> Explanation`; commentary continues to map `event.type` + context tags derived from projected score/minute/momentum. Live Discord may keep a **cached projection** updated per event for UI snappiness, but settlement and recovery **reproject from stored events** (or from regenerated stream when events not stored).

**Rationale**: FR-004; single SoT.

**Alternatives considered**: Keep authoritative live counters forever — rejected (diverges on recovery).

---

## R10 — Phase 0 behavioural parity

**Decision**: Port existing phase bases, `/55` divisor, 5% floor, momentum, stagnation, injury hooks as-is into v3 phases module. Golden corpus: freeze N seeds’ v2 event digests **before** port; v3 must match within documented allowances (ideally exact for no-decision matches).

**Rationale**: SC-008; managers should not feel a silent rebalance during Phase 0.

**Alternatives considered**: “Improve” balance during port — rejected (couples migrations).

---

## R11 — Injury interactive pause under step model

**Decision**: When step emits interactive `INJURY`, engine returns `StepResult.awaiting_decision=True` with legal actions; Discord presents UI; resolution enqueued as `SUB_RESOLUTION` / `PLAY_ON` decision; next `step` consumes it. Silent/auto: `BotBrain` or `auto_resolve_injury` fills inbox immediately (same as today’s auto path).

**Rationale**: Preserves Phase 3 UX without Discord inside the package.

---

## R12 — Schema versioning

**Decision**: `MatchEvent.schema_version: int` (start at 1); `match_runs.event_schema_version`; projectors switch on version; breaking changes get migrators or “replay with engine_version only” policy for ancient runs.

**Rationale**: FR-016.

# Research: Competitive Bot Match (057)

**Feature**: `057-competitive-bot-match`  
**Date**: 2026-08-08

## R1 — Extension point: NSS stream, not legacy `MatchSimulationResult`

**Decision**: Implement Competitive Match on the **live NSS v2/v3 streaming path** used by `battle_cog.execute_bot_battle` (`stream_match` / `stream_match_v3`, `MatchState` in `v2_simulator.py`), not as a parallel engine and not primarily via legacy `packages/match_engine/match_engine.py` interval simulation.

**Rationale**: Bot Battles already stream to stadium threads with commentary. The source brief’s file list (`match_engine.py`, `MatchSimulationResult`) describes the older Dixon-Coles/interval stack. Extending the dead path would leave `/battle bot` unchanged.

**Alternatives considered**:
- Port Bot Battles back to legacy interval engine — rejected (regress live stadium UX).
- Build `competitive_engine.py` — rejected (YAGNI / dual maintenance).

**Implication**: Phase enum, ET continuation, and FULL_TIME→ET transitions live in the stream lifecycle. `penalty_shootout.py` is still justified as an isolated pure module called when phase becomes `PENALTY_SHOOTOUT`.

## R2 — Restart safety requires new bot recovery durability

**Decision**: Before enabling Competitive Match in any guild, persist enough state to resume mid-ET and mid-shootout. Today `match_recovery` **abandons** interrupted bot/friendly runs (complete only if `match_history` exists).

**Rationale**: Spec FR-014/015/016 and US3. Without durable phase/kick state, ET/pens are not production-safe on Discord.

**Approach**:
- Extend `match_runs.squad_snapshot` (or dedicated JSONB column `competitive_state`) with: `match_phase`, `phase_minute`, `regulation_scores`, `et_scores`, `penalty_state`, sub-seeds.
- Prefer **deterministic sub-seeds** (`hash(sim_seed, "et1"|"et2"|"shootout")`) over serializing Python RNG.
- Flush `match_events` incrementally (or at phase boundaries) so recovery can skip completed work.
- `recover_interrupted_matches`: if competitive phase in progress and snapshot valid → resume stream; else keep abandon semantics for unrestorable runs.

**Alternatives considered**:
- Keep abandon-on-restart and accept broken ET — rejected (spec requires recovery).
- Full RNG object pickle — rejected (fragile across deploys).

## R3 — Economy: competitive resolution ≠ reward change (Phase 1)

**Decision**: Store `decided_by` ∈ {`regulation`,`extra_time`,`penalties`} (and pen tallies) for display/analytics, but **keep** existing bot coin/XP/fatigue/evolution settlement. No XP for penalty kicks; ET event volume does not create extra reward opportunities. `MATCH_MINUTES` for XP remains 90 unless a later calibrated change is approved.

**Rationale**: Spec FR-020 / SC-007. Prevents silent economy inflation while gameplay ships behind a flag.

## R4 — Discipline: live NSS cards vs suspension persistence

**Decision**:
1. Ensure live stream emits dismissal consequences compatible with second-yellow / straight-red (reuse legacy metadata lengths 1 / 2).
2. Persist suspensions in `player_suspensions` via settlement RPC.
3. Gate XI via `squad_validity` / bot battle injured-style checks.
4. Defer cross-match yellow accumulation.

**Rationale**: Legacy engine already attaches `suspension_matches` on card events but nothing persists. Live path is weaker today — must close that gap for Competitive Match.

## R5 — Extra time as continued stream, not new scorer

**Decision**: After regulation draw (flag on), continue the same interval/event generator for minutes 91–95 and 96–100 with config multipliers:
- `competitive_extra_time_fatigue_multiplier` default `1.35`
- `competitive_extra_time_injury_multiplier` default `1.25`

Fitness/discipline carry forward. No separate xG model.

## R6 — Penalty shootout module

**Decision**: New pure module `packages/match_engine/penalty_shootout.py` owns eligibility, ordering score, conversion probability (bounded 0.58–0.90), miss vs save distinction, early stop, sudden death, serializable state + deterministic kick events.

Derived composure: `consistency * 0.70 + morale * 0.30` (else consistency). GK reflexes: effective DEF/OVR already used by NSS — no new card attributes.

## R7 — Feature flags

**Decision**: Seed `game_config`:
- `competitive_match_enabled` → `false`
- `bot_dynamic_difficulty_enabled` → `true` (inert until Phase 6 wiring)
- ET/injury multipliers + difficulty deltas as numeric JSON

Env override: `COMPETITIVE_MATCH_ENABLED` (same pattern as other bot flags). Python resolves env then `game_config`.

## R8 — AI difficulty

**Decision**: Bound bot effective strength to manager club strength ± configured deltas (defaults about −4…+4 with optional offset). Build on existing `build_bot_match_squad` / division calibration. No invisible 99s, no rule exemptions, no shootout bonuses.

## R9 — Stadium presentation

**Decision**: Keep `StandardMatchHandler` / commentary engine. Add phase banners (ET start, ET break, pens start). Tier events A/B/C; buffer Tier C into stats/next digest. Shootout: one editable embed/message with emoji sequence. Discord failures never rewind simulation.

## R10 — Migration number

**Decision**: Forward migration `109_competitive_bot_match.sql` (after `108`). Extend `verify_required_schema.sql`.

## R11 — SDD / v1.0.0 docs

**Decision**: During implementation, update `.specify/specs/v1.0.0/spec.md` + `plan.md` for US-12 Bot Battle competitive phases (flag-gated), per AGENTS SDD rule — referenced in Phase 0 of rollout, executed with implement tasks.

## Resolved clarifications

No open NEEDS CLARIFICATION. Scope is Bot Battle only; ET is 5+5 abstraction; economy unchanged in Phase 1; NSS stream is the technical base.

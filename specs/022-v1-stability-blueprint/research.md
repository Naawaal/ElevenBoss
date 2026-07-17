# Research: v1 Stability Blueprint

**Feature**: `022-v1-stability-blueprint` | **Date**: 2026-07-15

## R1 — Verify-first vs rewrite-from-scratch

**Decision**: Wave 0 reclassifies every **Verify** registry item with greps + existing pytest before writing fix code. Only failed items become Open remediations.

**Rationale**: US-29 / economy / transfer / wages / MoMD / automation already claimed atomic pipes. Rewriting working RPCs risks regressions. Spec Success Criteria require confirmation, not archaeology.

**Alternatives considered**:
- Full rewrite of match reward paths — rejected (YAGNI; already wired via `apply_bot_match_rewards`).
- Trust status labels without greps — rejected (friendly double-tick history shows half-wired ships).

## R2 — SelectMenu disappearance root cause

**Decision**: Treat primary cause as **Discord Select requires ≥1 option** plus hub rebuilds that omit the Select (or leave a message with no guidance). Pattern: omit Select when empty; show embed empty-state field/footer; keep Back / re-open affordance. Shared helper in `view_helpers.py`.

**Rationale**: Hospital (`store_facilities.py`) and academy already add Select only `if patients` / `if waiting` — after last discharge the Select vanishes with no explanatory copy. Marketplace zero-filter same class. Timeout/stale is secondary (existing `disable_view_on_timeout`).

**Alternatives considered**:
- Placeholder disabled Select with a fake option — rejected (confusing values; Discord still shows a control that does nothing useful).
- Persistent Select custom_ids across bot restarts for ephemeral hubs — rejected (ephemeral hubs should re-run command; FR already allows recovery via command).
- New web UI for lists — rejected (out of scope / YAGNI).

## R3 — Legacy OVR inflation disposition

**Decision**: Wave 2 dry-runs `scripts/fix_inflated_player_stats.py`, records inflated count in registry Notes, then ops chooses **apply fair rebalance** or **defer with count**. New cards remain under factory True OVR equality asserts.

**Rationale**: Spec H3 forbids silent “maybe later.” Existing script + `detect_stat_inflation` already exist — reuse.

**Alternatives considered**:
- Always recompute overall on every display — rejected (drift vs stored columns; mentor/allocate already trust stored).
- Blind production apply without dry-run — rejected (player trust risk).
- Ignore legacy entirely — rejected (SC-004 / H3 require disposition).

## R4 — Evolution copy vs full overhaul (018)

**Decision**: Stability Wave 2 **B-Evo-Truth** only closes trust debt: slots/cooldown/cost copy aligned to live config/RPC; remove false PlayStyle promise. Full evolutions redesign stays in `018` if unfinished.

**Rationale**: Spec Out of Scope blocks new PlayStyle grant phase; YAGNI for stability. Managers care that numbers match reality.

**Alternatives considered**:
- Force complete 018 before v1 — rejected (blocks Critical money waves).
- Leave lying copy — rejected (H8 Open).

## R5 — Scheduler double-sim (Dynamics + interval)

**Decision**: Single cron owner is `league_state_machine_job` @ 00:05 (`main.py`). Interval `auto_sim_expired_fixtures_job` (10 min) must **skip** `pacing_mode='dynamics'` seasons. Wave 0 verifies skip; reopen E8/C4 if both process the same fixture.

**Rationale**: Spec 020/021 research already froze this; `dynamics_daily_tick_job` is a deprecated alias calling the state machine — only one cron registration exists. Residual risk is interval vs dynamics.

**Alternatives considered**:
- Remove interval entirely — rejected (legacy seasons still need soft close).
- Keep two crons with filters — rejected (021 chose fold to avoid misses).

## R6 — Feature flags during stability

**Decision**: Keep `wages_payroll_enabled`, `league_dynamics_enabled`, `league_automation_enabled` (and transfer enablement peers) **default off**. Pilot enable only after Wave exit gates; do not flip production defaults in this feature.

**Rationale**: Spec Assumption + SC-008. Stability proves edges; ops enablement is separate.

**Alternatives considered**: Force-enable all flags in staging only — allowed for pilots; not as repo default.

## R7 — Registry storage

**Decision**: Living status lives in `specs/022-v1-stability-blueprint/spec.md` Issue Registry (markdown). No `defect_registry` table.

**Rationale**: SDD is source of truth; DB table adds schema/RLS with no player value.

**Alternatives considered**: Linear/GitHub issues sync — optional later; not required for plan. Memory graph — empty for this project.

## R8 — Migration policy

**Decision**: No migration in the happy path. If Wave 0–1 proves broken uniqueness/guards, author **forward** `066_*` only; never edit applied 062–065 in place on remote.

**Rationale**: Schema Rule / AGENTS §8. Conditional Path documented in plan.

## R9 — Agent context script

**Decision**: Skip `.specify` agent-context update — script not present in this repo’s `scripts/` tree.

**Rationale**: Plan template step unavailable; human/AI context already loads AGENTS.md + this feature folder via Spec Kit feature.json.

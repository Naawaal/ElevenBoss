# Research: US-42.2 Player State Machine

**Feature**: `031-player-state-machine`  
**Date**: 2026-07-22  
**Status**: Complete

## R1 — Add a stored `primary_state` column?

**Decision**: **No** for MVP. Derive from existing flags (`is_retired`, `in_hospital`, `in_academy`, active listing, active evolution, squad assignment, `active_training`, club `match_locks`).

**Rationale**: A denormalized enum drifts from busy tables (022/017 already fought drift). Spec Assumptions allow flag-based derive.

**Alternatives considered**: Generated column / trigger-maintained enum — deferred until derive bugs prove need.

---

## R2 — Pure package vs SQL-only enforcement?

**Decision**: **Both** — pure `card_state.py` mirrors the matrix for UI hints + tests; SQL `assert_card_action_allowed(p_card_id, p_owner_id, p_action)` (name TBD) enforces inside RPCs.

**Rationale**: UI-only gates are bypassable (epic FR); SQL without pure mirror makes SC-001 hard and hubs inconsistent.

**Alternatives considered**: Pure-only — rejected (Discord can be skipped). SQL-only — rejected (no fast unit matrix tests / hub hints).

---

## R3 — One mega-assert vs keep scattered checks?

**Decision**: Introduce **one shared assert** that encodes exclusive busy + MatchLocked + action allow-list; keep specialized helpers (`assert_card_not_on_transfer_list`, `assert_not_in_match`) as callees or inline equivalents to avoid double-meaning. New/changed RPCs must call the shared assert; leave already-correct RPCs unless audit finds a gap.

**Rationale**: Ponytail — fix shared function once (AGENTS bug-fix rule); don’t churn every migration body blindly.

**Alternatives considered**: Rewrite all RPCs in 075 — rejected (huge risk, YAGNI).

---

## R4 — `TrainingBusy` reality

**Decision**: Treat `active_training` row as TrainingBusy when present (062 still checks it). If no row, state behaves as RosterFree/InXI. Do not invent a new training lock for instantaneous drills.

**Rationale**: Matches spec Assumptions; avoids false busy.

---

## R5 — InAcademy vs epic sketch

**Decision**: Keep **InAcademy** as exclusive primary (spec FR-020). Document in epic amendment note during implement if `029` sketch should gain the node (optional one-line update to `029` §5.1).

**Rationale**: Transfer/academy already treat academy as exclusive busy.

---

## R6 — MatchLocked vs card state

**Decision**: Overlay only — `assert_not_in_match(owner)` remains; shared assert also fails actions when lock present. Do not clear InXI on lock.

**Rationale**: Spec US4 / INV-17.

---

## R7 — Migration number

**Decision**: `075_player_card_state_guards.sql` (after 074).

---

## R8 — Scope of hub changes

**Decision**: Minimal — prefer RPC errors already clear; optional map known reason substrings in hubs. No new buttons.

**Rationale**: YAGNI; enforcement is the integrity win.

---

## Open items (non-blocking)

| Item | Owner |
|------|-------|
| Exhaustive edge catalog | US-42.10 |
| Listing purchase races | US-42.6 |
| Match settle + evo tick once | US-42.4 |
| Full reason-code enum table | Optional polish |

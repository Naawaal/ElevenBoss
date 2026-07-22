# Research: US-42 Game Integrity Epic

**Feature**: `029-game-integrity`  
**Date**: 2026-07-22  
**Status**: Complete (all planning unknowns resolved)

## R1 — Plan this epic for code, or for governance only?

**Decision**: Governance / delivery plan only. No production schema or cog changes authorized by `029` alone.

**Rationale**: The Locked epic framing states implementation is gated by child specs. A monolith implementation plan would force premature state machines and migrations across identity→marketplace simultaneously, violating YAGNI and creating unreviewable diffs.

**Alternatives considered**:
- Full-stack “integrity rewrite” wave — rejected (too broad; high regression risk).
- Skip `/speckit.plan` on epic — rejected (user requested plan; governance plan still valuable).

---

## R2 — Child feature numbering / folder strategy

**Decision**: Each child is a **new** Speckit feature under `specs/NNN-<short-name>/` (sequential after current max). Epic remains `029-game-integrity` as parent citation. Child `spec.md` MUST open with `Parent: specs/029-game-integrity` and `US-42.x` ID.

**Rationale**: Speckit is one-feature-per-specify; keeps history and tasks isolatable; matches user request for linked specs.

**Alternatives considered**:
- Subfolders only under `029/` without separate Speckit features — rejected (breaks specify/plan/tasks tooling and feature.json).
- One mega-spec with ten chapters — rejected (already decided against in specify).

---

## R3 — Delivery order

**Decision**: Prefer serial specify for P0 chain **42.1 → 42.2 → 42.3**, then **42.4** and **42.7** (can draft in parallel after 42.1), then overlays **42.5 / 42.6**, then **42.8**, then finalize **42.9** (may draft template early) and **42.10**. Implementation follows the same dependency edges; never implement conflicting domains in parallel.

**Rationale**: Ownership and exclusive states are prerequisites for match/market correctness. Economy registry (42.7) can proceed once identity is clear. League/market overlays must not fork `026`/`017`.

**Alternatives considered**:
- Spec all ten in one week before any Lock — allowed for drafting, but Lock order still follows deps.
- Implement economy integrity before identity — rejected (ownership is the root of reward claims).

---

## R4 — Relationship to `022-v1-stability-blueprint`

**Decision**: `022` remains the historical defect registry. Recurring defect *classes* become permanent invariants under US-42; do not reopen `022` as the ongoing constitution.

**Rationale**: Stability blueprint was a timeboxed remediation program. Integrity constitution is standing law.

**Alternatives considered**: Extend `022` forever — rejected (wrong lifecycle; mixes polish backlog with constitution).

---

## R5 — Relationship to `026` / `017` / US-25

**Decision**: Overlay model. US-42.5 / US-42.6 / US-42.7 cite and constrain; they do not rewrite sporting calendars, buy-it-now UX, or the economy pipe. Conflicts resolve via epic SoT matrix.

**Rationale**: Prevents forked league calendars and second coin pipelines — both known failure modes called out in AGENTS.md.

**Alternatives considered**: Merge league rulebook into US-42 — rejected (`026` already Locked for sport).

---

## R6 — Soft vs hard anti-abuse

**Decision**: Soft economic controls (floors, caps, tax, hold timers, idempotency) in-scope. Automated ban/detection systems out of scope for US-42 unless product amends epic Assumptions.

**Rationale**: Matches transfer-market assumptions and YAGNI; Discord false-positive bans are high support cost.

**Alternatives considered**: Device fingerprinting / alt graph — deferred indefinitely without product request.

---

## R7 — Where do shared “integrity helpers” live?

**Decision**: No new `packages/integrity`. Prefer extending `player_engine` (card gates/states), `economy` (registry mirrors), `leagues` (keys/catch-up helpers) when a child needs pure logic. App layer keeps Discord adaptation.

**Rationale**: Constitution monorepo boundaries + ponytail; a new package without clear API invites cross-feature imports.

**Alternatives considered**: `packages/game_integrity` — rejected until ≥3 children prove shared surface that does not fit existing packages.

---

## R8 — Idempotency key standards

**Decision**: Epic mandates every Logical Action declare a key strategy. Concrete key patterns are owned by domain children / existing specs (e.g. `match_run_id`, `league_entry:{season}:{player}`, payroll week keys). US-42.9 publishes a **template** for documenting keys on new RPCs; US-42.7 maintains economy source→key registry.

**Rationale**: Keys already exist in places; consolidating patterns beats inventing a global key service prematurely.

**Alternatives considered**: Central `idempotency_keys` table for all actions — possible later via 42.9 if gaps proven; not required for epic exit.

---

## R9 — Agent context / SDD adoption

**Decision**: No `update-agent-context` script exists in this repo’s `.specify/scripts`. Adoption = (1) keep epic as `feature.json` until child specify, (2) tasks to add short US-42 pointers in `AGENTS.md` and optionally `.specify/specs/v1.0.0/spec.md`.

**Rationale**: Tooling gap; manual pointer is enough for SC-001/SC-005.

**Alternatives considered**: Invent agent-context script now — rejected (out of epic scope).

---

## R10 — Exhaustive edge catalog timing

**Decision**: Category index lives in epic; exhaustive rows (≥100) only in US-42.10 after domain children exist so edges cite real states/actions.

**Rationale**: Writing hundreds of edges before state machines exist produces fiction and churn.

**Alternatives considered**: Fill 42.10 during epic plan — rejected (premature).

---

## Open items for children (not epic blockers)

| Item | Owner child |
|------|-------------|
| Inactive/Abandoned thresholds (days) | US-42.3 |
| Full card action×state matrix | US-42.2 |
| Match abandon / disconnect terminal rules | US-42.4 |
| Job catalog + run-key schema | US-42.8 |
| Faucet/sink living registry rows | US-42.7 |
| Threat model detail | US-42.10 |

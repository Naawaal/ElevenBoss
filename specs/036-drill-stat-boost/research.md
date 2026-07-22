# Research: Drill Attribute Boost

**Feature**: `036-drill-stat-boost` | **Date**: 2026-07-22

## R1 — Soft-fail attribute vs hard-fail whole drill

**Decision**: Soft-fail the attribute boost; always complete XP + cost accounting when other drill gates pass.

**Rationale**: Spec FR-004 / User Story 2 require XP when pot/99 blocks the attribute. Managers near potential should not lose the drill attempt.

**Alternatives considered**:
- Hard-fail entire drill at pot/99 → Rejected (contradicts FR-004; worse UX than today’s XP-only).
- Charge but skip XP when blocked → Rejected (spec says XP still awarded).

## R2 — Cap check before write (peek) vs apply-then-rollback

**Decision**: Pre-check with existing SQL `peek_card_ovr` (and 99 / `overall >= potential` short-circuits), then write only if legal.

**Rationale**: `allocate_skill_point` applies `+1` then `RAISE` if `recalculate_card_ovr > potential`, which aborts the whole transaction. Drill must keep economy + XP commits when boost is illegal, so allocate’s pattern is unsafe here. `peek_card_ovr` already exists (038) for projected OVR without mutating.

**Alternatives considered**:
- `SAVEPOINT` around boost then rollback savepoint → Works but heavier and less readable than peek.
- Trust stored `overall` only without projecting after `+1` → Rejected (skill allocation already projects; some `+1`s leave OVR flat, some raise it).

## R3 — Gate parity with skill allocation

**Decision**: Same ceilings as allocation / evolution: per-stat **99**, and projected overall must not exceed **potential**. Pure UI preview reuses `can_allocate_skill_point` (does not require available SP).

**Rationale**: Spec Assumptions; `can_allocate_skill_point` already models trial `+1` + `calculate_true_ovr`. Avoid inventing a second gate.

**Alternatives considered**:
- Only block when `overall >= potential` without projecting → Weaker than allocation; can overshoot pot on the write that tips OVR.
- New `can_drill_stat_boost` wrapper → Optional thin alias later; YAGNI for MVP if call sites use existing helper.

## R4 — Mutation home and migration number

**Decision**: Single forward migration **`078_drill_stat_boost.sql`** replacing `process_stat_drill` from the **075** body (retains `assert_card_action_allowed(..., 'drill')`, transfer-list + match locks, soft-reset, 20/5 caps, economy + XP).

**Rationale**: AGENTS schema rule — never edit applied migrations in place. Latest drill body with integrity guards is in 075. Next free number after 077 is 078. No new columns (FR-010).

**Alternatives considered**:
- Client-side attribute UPDATE after XP RPC → Violates DB rule / race-prone / double-write risk.
- Separate `apply_drill_stat_boost` RPC called from cog after drill → Extra round-trip and non-atomic with XP/costs.

## R5 — Boost size and multi-stat drills

**Decision**: Always **`+1`** regardless of basic/advanced tier. No multi-stat drills in catalog — out of scope.

**Rationale**: Spec assumptions; `DRILL_CATALOG` already maps each id to one `stat`. Tier continues to drive energy/XP/coins only.

**Alternatives considered**:
- Advanced tier `+2` → Spec says modest +1; would accelerate pacing beyond SC-004’s “≤5/card/day” mental model if both tiers stack higher.
- Let manager pick which attribute on a “Physical” drill → No such drill exists.

## R6 — RPC response and UI honesty

**Decision**: Additive JSON fields on existing success payload; hub parser defaults missing fields to “no boost info”; select preview + summary distinguish boosted vs blocked.

**Rationale**: Spec FR-006 / User Story 3. Back-compat if an old bot talks to new RPC or vice versa during deploy.

**Alternatives considered**:
- Only raise human-readable exceptions for blocks → Would abort XP (rejected by R1).
- Silent skip with no reason → Violates FR-004.

## R7 — Docs drift (US-23 XP-only)

**Decision**: On implement, amend AGENTS.md drills bullet, `.specify/specs/v1.0.0` AC-23f / related “XP only” lines, and `change_log.md`.

**Rationale**: Spec Assumptions; shipping code without SDD/agent rule updates will cause the next agent to “fix” the boost away.

**Alternatives considered**: Leave docs stale → Rejected (AGENTS Section 5 + wiring discipline).

## R8 — Integrity interaction (US-42.2)

**Decision**: Preserve `assert_card_action_allowed(..., 'drill')` and existing eligibility locks; this feature does not widen drill eligibility.

**Rationale**: Child 031 already flagged drills; 078 must not drop the assert when replacing the function body.

**Alternatives considered**: N/A — dropping the assert would regress integrity.

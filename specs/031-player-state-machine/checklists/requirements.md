# Specification Quality Checklist: Player State Machine (US-42.2)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **Integrity-child exception**: Informative proof tables (e.g. `active_evolutions`, `match_locks`) and INV IDs appear for continuity with Locked epic/domain specs — not new stack choices. FR/SC stay outcome-oriented.
- **Epic extension**: `InAcademy` added as exclusive primary state (FR-020) — justified by academy + transfer rules; does not weaken INV-03.
- **Child template**: Sections A–G included; full action matrix in §B.5.
- Validation iteration: 1 — all items pass.
- Ready for `/speckit.clarify` (optional) or `/speckit.plan`.

### W0 gap priority (implement)

Critical (075 must wire): `admit_to_hospital`, `start_player_evolution`, `process_stat_drill`, `swap_squad_players`.

Soft (wire assert when cheap): cancel listing, claim/cancel evo, fusion, allocate, agent_sale, discharge, academy promote/release, retire.

Unique busy indexes retained: `idx_active_evolutions_active_card` (020); listing uniqueness via `assert_card_not_on_transfer_list` / active listing checks — not weakened by 075.

Exit actions (`cancel_listing`, `discharge_hospital`, `claim_evolution`, `cancel_evolution`, academy promote/release) Allowed by matrix when in that busy state; assert must not Block those exits (MatchLocked still Blocks per §B.5).

Enforcement + player-facing: `change_log.md` updated with busy-card / CARD_STATE guidance (US-42.2).

# Feature Specification: Fix Match XP + Energy Regen

**Feature Branch**: `001-fix-match-xp-energy`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "bug reported: after playing match xp are not granted; energy refill 10hr is too long"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Match XP After Bot or League Match (Priority: P1)

As a manager, after I finish a bot battle or a league match, my starting players earn development XP so the match feels rewarding and squads progress over time.

**Why this priority**: Missing match XP breaks the core progression loop for the two competitive match types that are supposed to grant it. This is a reported production bug.

**Independent Test**: Complete one bot match (and separately one league match) with cards under the daily match-XP limit; confirm each eligible starting card’s XP or level increased afterward.

**Acceptance Scenarios**:

1. **Given** a manager completes a bot match and at least one starting card is under the daily match-XP limit and not at max level, **When** match rewards are applied, **Then** that card’s development XP increases.
2. **Given** a manager completes a league match under the same eligibility conditions, **When** match rewards are applied, **Then** that card’s development XP increases.
3. **Given** a card has already reached its daily match-XP limit, **When** another bot or league match completes, **Then** the match still finishes successfully and that card gains no further match XP for the day.
4. **Given** the XP grant path hard-fails (system error), **When** the match otherwise completes, **Then** the manager is not left believing rewards succeeded with no indication that XP failed.

---

### User Story 2 - Faster Passive Energy Regen (Priority: P2)

As a manager, when my action energy is empty, waiting for a full refill through passive regeneration takes about six and a half hours—not about ten—so short daily sessions are viable without mandatory coin refills.

**Why this priority**: A ~10-hour empty-to-full wait is a reported pain point; the approved rebalance target is ~6 hours 40 minutes at max energy 100.

**Independent Test**: With energy at 0 of 100, confirm the effective regen rate implies ~6h 40m to full, and that hub/status text matches that rate (not a stale 6-minutes-per-point / ~10h message).

**Acceptance Scenarios**:

1. **Given** a club has 0 of 100 action energy, **When** passive regeneration runs at the approved rate, **Then** empty-to-full takes approximately 6 hours 40 minutes.
2. **Given** a manager views energy status or an insufficient-energy error, **When** the bot shows regen timing, **Then** the displayed rate matches the effective approved rate (no stale “every 6 minutes” or implied ~10h full refill).

---

### User Story 3 - Friendlies Stay Sandbox (Priority: P3)

As a manager, friendly matches remain a free practice sandbox: no energy spent and no XP earned, so the XP fix does not change friendly design.

**Why this priority**: Confirms scope boundary so the XP fix is not misapplied to friendlies.

**Independent Test**: Play a friendly; confirm no energy spent and no card XP granted; footer/copy still indicates no XP/coins.

**Acceptance Scenarios**:

1. **Given** a manager completes a friendly match, **When** the match ends, **Then** no action energy is spent and no card XP is granted.

---

### Edge Cases

- What happens when a card is already at max level? Match completes; that card gains 0 XP without blocking other cards.
- What happens when daily match-XP cap is exhausted mid-session? Later matches still complete; further match XP for that card is 0 until the daily reset.
- What happens when only some starting cards are eligible? Eligible cards gain XP; ineligible cards do not; match still succeeds.
- How does the system handle a hard failure in the XP grant path? Match outcome and other rewards must not silently imply XP succeeded; the manager gets a clear failure signal for the XP portion.
- What if production still uses the old slower regen? Shipping this feature includes bringing live regen to the approved faster rate and aligning visible copy.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After a completed bot match, the system MUST grant match development XP to each eligible starting card that is under the daily match-XP limit and not at max level.
- **FR-002**: After a completed league match (human-managed path), the system MUST grant match development XP under the same eligibility rules as bot matches.
- **FR-003**: When a card cannot receive match XP because the daily match-XP limit is exhausted or the card is at max level, the match MUST still complete successfully and that card MUST receive 0 additional match XP.
- **FR-004**: When the match XP grant path hard-fails, the system MUST surface a clear failure indication to the manager rather than implying XP was applied.
- **FR-005**: Passive action energy MUST regenerate at the approved faster rate such that empty-to-full at max 100 takes approximately 6 hours 40 minutes (1 energy per 4 minutes).
- **FR-006**: Player-visible energy status and insufficient-energy messaging MUST reflect the effective approved regen rate (no stale 6-minutes-per-point or ~10-hour full-refill messaging).
- **FR-007**: Friendly matches MUST continue to spend no action energy and grant no card XP.
- **FR-008**: Coin-based energy refills in the store (amount, escalating costs, daily purchase cap) MUST remain unchanged by this feature.
- **FR-009**: The existing daily match-XP cap per card MUST remain in force; this feature restores broken grants, it does not remove the cap.

### Key Entities

- **Match (bot / league / friendly)**: A completed simulation; bot and league grant development XP; friendly does not.
- **Player card**: Squad member that accumulates development XP and levels; subject to daily match-XP limit and max level.
- **Action energy**: Club resource that regenerates passively over time up to a maximum; spent on competitive actions, not on friendlies.
- **Daily match-XP allowance**: Per-card daily limit on XP earned from matches; when exhausted, further match XP for that card is zero until reset.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In verification of a bot match with eligible cards under the daily match-XP limit, 100% of those eligible starting cards show increased development XP after rewards apply.
- **SC-002**: In verification of a league match under the same conditions, 100% of eligible starting cards show increased development XP after rewards apply.
- **SC-003**: Empty-to-full passive energy at max 100 completes in approximately 6 hours 40 minutes (±5 minutes), not approximately 10 hours.
- **SC-004**: Energy status and insufficient-energy messages shown to managers match the effective regen rate (no contradictory “6 minutes” / ~10h full messaging).
- **SC-005**: Friendly matches continue to grant 0 XP and spend 0 energy in 100% of verification runs.
- **SC-006**: Hard failure of the XP grant path produces a manager-visible failure indication in 100% of simulated hard-failure checks (no silent “success with no XP”).

## Assumptions

- Scope is bot and league match XP only; friendlies intentionally grant no XP.
- Approved energy target is the existing rebalance: ~6h 40m empty-to-full (1 per 4 minutes at max 100), not a further reduction.
- Daily match-XP cap of 100 per card per day remains; managers who already hit the cap may still perceive “no XP” after several matches—that is expected pacing, not this bug.
- Store coin energy refills (+50, escalating costs, max 3/day) are out of scope and unchanged.
- Match energy costs beyond the already-approved bot cost reduction in the rebalance are out of scope.
- Production may still be on the slower regen rate and/or a broken XP grant path; this feature includes bringing live behavior in line with the requirements above.
- Managers verify XP primarily via card XP/level after the match; richer post-match XP breakdown UI is optional and not required for this fix unless needed to satisfy FR-004.

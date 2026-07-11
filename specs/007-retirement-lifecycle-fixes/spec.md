# Feature Specification: Retirement Lifecycle Fixes

**Feature Branch**: `007-retirement-lifecycle-fixes`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Surgical fixes to the existing retirement system: (1) close the aging-curve gap so SHO/DRI also decline for veterans; (2) prevent squad holes after retirement via bench auto-promote or a squad-invalid gate before matches; (3) rewrite regen rarity so high-OVR legends spawn Rare/Epic prospects instead of mostly Commons."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Veterans Lose All-Around Edge (Priority: P1)

As a manager keeping aging attackers in the starting XI, I see their close control and finishing decline in late career—not only pace and physique—so retired stars feel naturally washed up rather than immortal finishers who only got slower.

**Why this priority**: Closing the immortal-shooter exploit is the highest-impact balance fix; without it, veteran strikers remain a permanent min-max trap.

**Independent Test**: Age a card through years 31→36 under the season-aging rules and verify every core attribute that should decline at each band has decreased (including dribbling from 33+ and shooting from 35+), with retirement still occurring at the existing retirement age.

**Acceptance Scenarios**:

1. **Given** an active card whose age advances into 33 or 34 during season aging, **When** decline is applied for that year, **Then** dribbling decreases by 1 (floored at the existing minimum of 1), in addition to any other declines already defined for that age band.
2. **Given** an active card whose age advances into 35 or older during season aging (before retirement), **When** decline is applied for that year, **Then** shooting decreases by 1 (floored at 1), so by retirement every core attribute is on a downward path for late veterans.
3. **Given** a card still below the veteran decline bands, **When** season aging runs without a birthday year change into those bands, **Then** shooting and dribbling are unchanged by the new late-career rules.

---

### User Story 2 - Retirement Does Not Leave a Silent Squad Hole (Priority: P1)

As a manager whose starting player retires overnight, I either get an automatic bench replacement in that slot or a clear block before kickoff telling me to fix my lineup—so I never start a match with an incomplete XI by accident.

**Why this priority**: Match integrity and immersion; a missing starter after Monday retirement is the most painful live UX failure of the current lifecycle.

**Independent Test**: Retire a starting-XI card for a club that has an eligible bench player of the same position, and separately for a club with no eligible bench cover; confirm auto-fill vs. invalid-squad gate behavior without starting a broken match.

**Acceptance Scenarios**:

1. **Given** a starting-XI slot’s card retires and at least one bench player is eligible for that vacated position, **When** retirement completes, **Then** one eligible bench player is auto-assigned into the vacated starting slot and the club is not marked squad-invalid solely because of that retirement.
2. **Given** a starting-XI slot’s card retires and no eligible bench player can cover that position, **When** retirement completes, **Then** the vacancy remains and the club is flagged as having an invalid starting XI.
3. **Given** a club is flagged squad-invalid after retirement, **When** the manager tries to start any match, **Then** the match does not begin and they receive clear guidance to visit squad management and set a valid lineup.
4. **Given** a club flagged squad-invalid, **When** the manager saves a complete valid starting XI via `/squad`, **Then** the invalid flag clears and match starts are allowed again. (Flag may also clear earlier if a later retirement auto-promote restores 11 starters.)
5. **Given** a starter retires and an eligible reserve is auto-promoted so the club again has 11 starters, **When** retirement completes, **Then** `squad_invalid` is false and match starts are not blocked solely due to that retirement.

---

### User Story 3 - Legend Regens Feel Like Legends (Priority: P2)

As a manager scouting the regen market after a high-OVR retirement, I expect Rare or Epic youth prospects from true legends—not a majority of Commons—so reincarnating a dominant player feels rewarding and the scouting pool stays premium.

**Why this priority**: Economy/fantasy payoff of retirement; less urgent than match-blocking squad holes but critical for long-term immersion and market value.

**Independent Test**: Generate many regens from retired cards in each peak-OVR band (75–79, 80–84, 85+) and confirm rarity frequencies match the proportional bands below (within sampling tolerance).

**Acceptance Scenarios**:

1. **Given** a retired card with peak overall ≥ 85 that qualifies for regen spawn, **When** a regen is generated, **Then** rarity is Epic or Rare only (never Common), with equal weight between Epic and Rare.
2. **Given** a retired card with peak overall 80–84 that qualifies for regen spawn, **When** a regen is generated, **Then** rarity is Rare with 60% weight and Common with 40% weight (no Epic from this band).
3. **Given** a retired card with peak overall 75–79 that qualifies for regen spawn, **When** a regen is generated, **Then** rarity is Common with 80% weight and Rare with 20% weight.
4. **Given** a retired card below the existing regen eligibility threshold, **When** retirement completes, **Then** no regen listing is created (unchanged eligibility gate).

---

### Edge Cases

- Multiple starters retire in the same aging batch for one club → each vacancy is resolved independently (auto-promote if possible; otherwise the club ends invalid if any starting slot remains empty).
- Bench has multiple eligible covers for one vacated position → one eligible player is chosen deterministically or fairly; remaining bench players stay on the bench.
- Retired card was already on the bench only → starting XI is unchanged; club is not flagged invalid solely for a bench retirement.
- Retired card was not in any squad assignment → no vacancy handling; no invalid flag.
- Auto-promote candidate is injured, fatigued, or otherwise match-restricted → still eligible for assignment under this feature (match readiness remains a separate concern); do not leave a hole solely because of temporary status.
- Club already had an incomplete XI before retirement → invalid flag remains or is set; match start stays blocked until a valid XI is saved.
- Attributes already at floor (1) → further decline for that attribute is a no-op at the floor.
- Double season-aging / idempotent retirement → already-retired cards are not declined or re-retired; regen spawn remains one listing per eligible source.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Season aging MUST continue to derive age from date of birth and apply decline only when cached age advances year-over-year (existing lifecycle timing unchanged).
- **FR-002**: For each advanced year at age ≥ 31, pace and physique MUST continue to decline per the existing veteran curve (including the stronger drop at age ≥ 35).
- **FR-003**: For each advanced year at age ≥ 33, passing and defending MUST continue to decline by 1 each (existing rule), and dribbling MUST also decline by 1.
- **FR-004**: For each advanced year at age ≥ 35 (while still active), shooting MUST decline by 1, so late veterans trend downward on all six core attributes before retirement.
- **FR-005**: Attribute decline MUST never reduce a core attribute below 1; overall MUST be recalculated after decline as today.
- **FR-006**: Retirement age, warning age, and DOB-based age calculation MUST remain unchanged by this feature.
- **FR-007**: When a card is retired, it MUST be removed from squad assignments (existing behavior).
- **FR-008**: If retirement removes a starting-XI player and an eligible bench player exists for that position, the system MUST auto-assign one such bench player into the vacated starting slot as part of the same retirement resolution.
- **FR-009**: “Eligible for position” MUST mean the bench player’s primary position matches the vacated starting slot’s position under existing squad position rules (no new dual-position matrix in this feature).
- **FR-010**: If retirement leaves a starting-XI vacancy with no eligible bench cover, the club MUST be marked squad-invalid.
- **FR-011**: Match start flows (bot, friendly, and league) MUST refuse to begin when the club is squad-invalid, with clear copy directing the manager to squad management.
- **FR-012**: The `squad_invalid` flag is cleared automatically if retirement resolution successfully auto-promotes reserve players to restore a valid 11-player starting XI. If auto-promotion cannot fill the holes (e.g. empty reserves), the flag remains `TRUE` and is only cleared manually when the manager saves a valid 11-player lineup via `/squad`.
- **FR-013**: Regen spawn eligibility MUST remain peak overall ≥ 75 (and other existing pool rules: position inheritance, age 16–19, OVR band, pool cap, idempotency).
- **FR-014**: Regen rarity MUST use peak overall of the retired card with these exact weights:
  - ≥ 85: 50% Epic, 50% Rare, 0% Common
  - 80–84: 60% Rare, 40% Common, 0% Epic
  - 75–79: 80% Common, 20% Rare, 0% Epic
- **FR-015**: This feature MUST NOT introduce new slash commands, hubs, or tables; it may extend existing club/player state with a squad-validity flag and adjust existing aging/retirement/regen behavior only.
- **FR-016**: Managers MUST NOT need a new UI surface beyond clearer match-block messaging and the existing `/squad` path to repair an invalid lineup.

### Key Entities

- **Player Card**: Active or retired roster member with date of birth, cached age, six core attributes, overall, and retirement state.
- **Starting XI Vacancy**: A formation slot left empty when its assigned card retires.
- **Squad Validity Flag**: Club-level mark indicating the starting XI is incomplete or otherwise unsafe to take into a match after retirement fallout.
- **Bench / Reserve**: An owned player card not currently assigned to one of the 11 starting slots in `squad_assignments`. There is no separate bench table — “bench” and “reserve” mean this pool. Auto-promotion pulls from it by highest overall, then lowest card id. A **bench cover** for a vacancy is a reserve whose primary position matches the vacated slot’s formation role.
- **Regen Prospect**: Youth listing spawned from an eligible retired card, with rarity weighted by the retiree’s peak overall.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In scripted aging through ages 33 and 35, 100% of test cards show dribbling decline at 33+ and shooting decline at 35+, with no card retaining immortal shooting/dribbling while other late-career stats fall.
- **SC-002**: In 100% of retirement cases with eligible same-position bench cover, the vacated starting slot is filled automatically and a subsequent match start is not blocked solely due to that retirement.
- **SC-003**: In 100% of retirement cases that leave an empty starting slot with no eligible cover, match start is blocked with actionable squad-repair guidance until a valid XI is saved.
- **SC-004**: Across large regen samples from ≥85 OVR retirees, Common rarity rate is 0% and Epic/Rare each land near 50% (±5 percentage points at n≥200).
- **SC-005**: Across large regen samples from 80–84 and 75–79 bands, observed Rare/Common rates match the specified weights within ±5 percentage points at n≥200 per band.
- **SC-006**: Zero matches begin with fewer than 11 starting assignments caused by an unhandled retirement vacancy after this feature ships.

## Assumptions

- Existing Monday season-aging batch and retirement warning/retire ages (35 warn / 36 retire) remain the schedule; this feature only deepens decline math and vacancy handling.
- Existing regen OVR/age/position/pool-cap/idempotency rules stay; only rarity weighting changes.
- “Peak overall” for rarity means the retired card’s overall at (or used for) regen generation today—no new historical peak tracking table.
- Auto-promote prefers the eligible same-role reserve with highest overall, then lowest card id; no manager input required.
- Temporary match-fitness states (injury/fatigue) do not block auto-promote in this slice.
- `squad_invalid` clears automatically when auto-promote restores an 11-player starting XI; otherwise it stays `TRUE` until the manager saves a valid full starting XI via `/squad` (not cleared by login or opening profile alone).
- Bot-controlled clubs follow the same retirement vacancy rules; if left invalid, automated match paths that require that club must skip or fail safe rather than simulate with a hole (see tasks T014 / T014b).
- No marketplace UI redesign; rarity still appears on existing scouting listings.
- Player-facing changelog should note the three balance/UX fixes when this ships.

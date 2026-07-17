# Feature Specification: Gacha Pack Epic Cap (No Legendary Drops)

**Feature Branch**: `024-gacha-no-legendary`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "Legendary players must no longer appear in any gacha pulls; highest pack rarity is Epic. Audit odds, remove Legendary from drop pool, update UI copy, keep existing Legendaries, prefer configurable odds, simulate large pack openings to prove zero Legendary drops. Aligns with Legendaries being special-event only."

## Background & Motivation

Daily player packs currently include **Legendary** at a small weight (published historically as Common 60% / Rare 30% / Epic 8% / Legendary 2%). After the Recover update, Legendary cards are reserved for **special thank-you / event grants**, not random pack luck. Packs must stop dropping Legendary while leaving owned Legendary cards and event grant paths intact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Packs Never Drop Legendary (Priority: P1)

As a manager claiming a daily pack, every card I receive is Common, Rare, or Epic — never Legendary.

**Why this priority**: This is the entire product change. Without a hard zero Legendary rate, event exclusivity fails.

**Independent Test**: Open many packs (automated simulation of thousands of cards); count of Legendary rarity is exactly 0; Epic remains possible.

**Acceptance Scenarios**:

1. **Given** the updated pack rules are live, **When** a manager claims a daily pack of 5 players, **Then** every card’s rarity is one of Common, Rare, or Epic.
2. **Given** pack generation runs for a large simulated sample (e.g. ≥10,000 cards), **When** rarities are tallied, **Then** Legendary count is **0**.
3. **Given** any named pack product that previously included Legendary in its mix, **When** that pack is generated, **Then** Legendary is absent from the selectable rarity list / weights (weight effectively 0, not merely “very rare”).

---

### User Story 2 - Odds Are Clear and Tunable (Priority: P1)

As ops / product, I can see and adjust pack rarity odds without rediscovering hardcoded magic numbers, and managers are not told Legendary is a pack outcome.

**Why this priority**: Prevents silent regression and supports future tuning without code deploys when config is wired.

**Independent Test**: Published pack odds show Common / Rare / Epic only; ops can change weights via game configuration (or documented package defaults if config read fails) and pack rolls follow them.

**Acceptance Scenarios**:

1. **Given** player-facing Store / pack copy that describes possible rarities or odds, **When** a manager reads it, **Then** it lists **Epic** as the maximum pack rarity and does **not** advertise Legendary as obtainable from packs.
2. **Given** pack rarity weights are stored in game configuration (with safe package defaults), **When** ops updates those weights without changing application code, **Then** subsequent pack opens use the new weights (after normal config refresh / process restart as the platform already does for other config keys).
3. **Given** configuration is missing or invalid, **When** a pack is generated, **Then** the system falls back to documented Epic-capped defaults and still never rolls Legendary.

---

### User Story 3 - Existing Legendaries and Event Grants Stay Valid (Priority: P2)

As a manager who already owns a Legendary (or receives one from a special gift), my card is unchanged and event grant paths still work.

**Why this priority**: Removes pack access without deleting prestige or breaking the thank-you Legendary feature.

**Independent Test**: An existing Legendary card still displays and plays; the support Legendary claim path can still grant a Legendary when that feature is enabled.

**Acceptance Scenarios**:

1. **Given** a club already owns Legendary cards, **When** packs stop dropping Legendary, **Then** those cards remain on the roster with rarity Legendary and normal gameplay rules.
2. **Given** a special-event Legendary grant feature is enabled (e.g. thank-you gift), **When** an eligible manager claims it, **Then** they can still receive a Legendary — this path is **not** a gacha pack pull.
3. **Given** marketplace, squad, and profile UIs that display rarity icons for owned cards, **When** a Legendary is shown, **Then** Legendary styling may remain for owned cards (display of owned rarity ≠ pack drop advertising).

---

### Edge Cases

- Starter onboarding squad generation must not introduce Legendary via the pack rarity table (today it uses Rare/Epic marquee + Common youth — must stay Legendary-free).
- Youth academy / regen / scouting paths are **out of scope** unless they currently call the same pack rarity table; if they do, they must not pull Legendary from that shared pack table either. Dedicated regen rarity rules for retirement remain separate.
- Invalid config (weights that include Legendary, or sum to zero): treat as Epic-capped safe defaults; never roll Legendary.
- Partial weight lists: Legendary weight if present must be ignored or forced to 0.
- Pity systems: if none exist today, do not invent one; if any Legendary pity exists, it must be removed or retargeted so it cannot grant Legendary from packs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Daily / standard gacha pack generation MUST NOT produce cards with rarity Legendary.
- **FR-002**: The highest rarity obtainable from pack pulls MUST be Epic.
- **FR-003**: Legendary’s former pack weight MUST be removed from the drop pool; remaining Common / Rare / Epic weights MUST be updated so probabilities remain valid (default approach: fold the former Legendary weight into Epic — see Assumptions).
- **FR-004**: Pack rarity odds MUST be readable from game configuration for the live standard pack, with package-level Epic-capped defaults used when config is absent or invalid.
- **FR-005**: Player-facing Store / pack claim copy MUST NOT list Legendary as a pack outcome; if odds are shown, they MUST match the Epic-capped mix.
- **FR-006**: Existing Legendary cards in clubs MUST remain unchanged by this feature.
- **FR-007**: Non-pack Legendary grant paths (e.g. support thank-you gift) MUST remain able to grant Legendary when those features are enabled.
- **FR-008**: Automated tests MUST simulate a large number of pack card rolls and assert zero Legendary outcomes under the new rules.
- **FR-009**: SDD / player changelog MUST be updated so published pack odds no longer claim Legendary 2%.

### Key Entities

- **Pack rarity mix**: Named pack product’s ordered rarities + weights used when rolling each card.
- **Daily pack claim**: Existing Store free pack (5 cards) that calls pack generation.
- **Owned player card rarity**: Persisted rarity on cards already in clubs; not rewritten by this feature.
- **Special Legendary grant**: Event/thank-you path outside pack generation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a simulation of at least **10,000** independently rolled pack cards under standard pack rules, Legendary count = **0**.
- **SC-002**: In the same simulation, Epic share is within a reasonable band of the published Epic-capped weights (e.g. within ±2 percentage points of expected for large N).
- **SC-003**: 100% of audited Store / pack-odds player-facing strings no longer promise Legendary from packs after ship.
- **SC-004**: Spot-check of pre-existing Legendary roster cards still shows rarity Legendary after deploy.
- **SC-005**: Support thank-you Legendary claim (when enabled) can still succeed for an eligible test account.

## Assumptions

- Current live standard pack mix before this change is approximately **60 / 30 / 8 / 2** (Common / Rare / Epic / Legendary).
- Default redistribution: fold Legendary’s **2** weight into Epic → **60 / 30 / 10** (Common / Rare / Epic). Ops may retune via config later.
- There is no pack pity timer that grants Legendary today; none will be added.
- Starter squad and youth intake do not need Legendary removal beyond ensuring they do not call a Legendary-inclusive pack table.
- Marketplace / squad **display** of Legendary for owned cards stays; only pack **acquisition** and pack **odds advertising** change.
- `generate_support_legendary` (thank-you gift) is intentionally outside this change’s ban.

## Out of Scope

- Deleting or converting existing Legendary cards
- Retuning Epic OVR bands or Legendary OVR bands for owned cards
- New paid pack SKUs
- Changing Division names that include the word “Legendary”
- Disabling the support Legendary thank-you gift feature (separate flag)

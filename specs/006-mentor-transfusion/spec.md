# Feature Specification: Mentor Transfusion

**Feature Branch**: `006-mentor-transfusion`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Pre-integration assessment + Mentor Transfusion gameplay — convert surplus skill points on potential-maxed cards into mentor points that accelerate non-maxed club mates via the Development hub, with daily transfer pacing and an 80% conversion tax."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transfer Mentor Progress From a Maxed Card (Priority: P1)

As a manager with a card that has reached its potential ceiling and still holds surplus skill points, I can convert those points into mentor progress and grant experience to a non-maxed card on my club, so legends stop being a dead end for development.

**Why this priority**: This is the core value of the feature — turning unspendable SP into a purposeful academy pipeline.

**Independent Test**: With one potential-maxed card holding at least 5 SP and one eligible non-maxed club mate, complete a Mentor Transfer for the minimum amount; confirm source SP decreases, target level/XP increases, and the action is recorded against the daily transfer limit.

**Acceptance Scenarios**:

1. **Given** a club-owned card at potential ceiling with at least 5 available skill points and a non-maxed club mate, **When** the manager completes a Mentor Transfer for a chosen mentor amount, **Then** the source loses the corresponding skill points, the target gains the converted experience in one atomic action, and both cards remain on the same club.
2. **Given** a successful transfer that would level the target past one or more levels, **When** the transfer completes, **Then** the target’s level and unlocked skill points follow the existing leveling rules (including potential/level ceilings already enforced by the progression system).
3. **Given** a manager attempts a transfer that would exceed the remaining convertible balance (less than 5 SP, or more mentor units than available), **When** they confirm, **Then** the transfer is rejected with a clear reason and no SP or XP changes.

---

### User Story 2 - Discover Mentor From Development Allocate Skills (Priority: P1)

As a manager opening Allocate Skills on a potential-maxed card, I see Mentor Transfer instead of a dead-end allocate experience, so I know surplus SP has a use without learning a new command.

**Why this priority**: Discovery must live on the existing Development path managers already use when SP is stuck.

**Independent Test**: Open `/development` → Allocate Skills on a potential-maxed card with SP ≥ 5; confirm Mentor Transfer is offered and leads to target + amount selection with a confirmation preview.

**Acceptance Scenarios**:

1. **Given** a potential-maxed card with convertible SP (≥ 5), **When** the manager opens Allocate Skills for that card, **Then** they see Mentor Ready messaging (available SP and convertible mentor units) and a Mentor Transfer action instead of only failing allocate attempts.
2. **Given** a non-maxed card with SP > 0, **When** the manager opens Allocate Skills, **Then** the existing six-stat allocate flow is unchanged (no Mentor Transfer required).
3. **Given** a potential-maxed card with fewer than 5 SP, **When** the manager views Allocate Skills, **Then** Mentor Transfer is unavailable with clear “need 5 SP” guidance and no silent failure.

---

### User Story 3 - Choose Target and Amount With Preview (Priority: P2)

As a manager, I pick which non-maxed club mate receives mentor progress and how much to send (quick amounts or max), and I see a confirmation preview of SP spent and expected level impact before committing.

**Why this priority**: Strategic choice (who / how much) is the engagement loop; preview prevents accidental dumps.

**Independent Test**: From Mentor Transfer, select a target from eligible cards, choose 1 / 3 / 5 / Max mentor units, confirm the preview matches the conversion rules, then cancel once and complete once.

**Acceptance Scenarios**:

1. **Given** Mentor Transfer is open, **When** the manager views targets, **Then** only same-club non-maxed cards appear (sorted to favor lower-level academy options first).
2. **Given** a chosen target and amount, **When** the confirmation preview is shown, **Then** it shows SP to deduct, mentor units granted, XP equivalent, and an expected level-up summary for the target.
3. **Given** the manager cancels on confirmation, **When** they return, **Then** no SP or XP has changed.

---

### User Story 4 - See Mentor Ready on Player Profile (Priority: P3)

As a manager viewing a potential-maxed card’s profile, I see that surplus SP is Mentor Ready and how many mentor units it converts to, so I notice the feature without opening Development first.

**Why this priority**: Improves discoverability; not required for the transfer to work.

**Independent Test**: Open player profile on a potential-maxed card with SP and on a non-maxed card; only the maxed card shows Mentor Ready conversion copy.

**Acceptance Scenarios**:

1. **Given** a potential-maxed card with available SP, **When** the manager opens its player profile, **Then** Skill Points shows Mentor Ready status and convertible mentor units / XP equivalent.
2. **Given** a non-maxed card, **When** the manager opens its player profile, **Then** Skill Points display remains the existing simple available-SP presentation (no mentor chrome).

---

### User Story 5 - Daily Transfer Pacing (Priority: P2)

As a manager with several maxed legends, I can complete at most three Mentor Transfers per club per day, so academy acceleration stays paced and cannot dump an entire season of surplus SP in one session.

**Why this priority**: Daily cap is the primary anti-front-load brake called out in the product design.

**Independent Test**: Complete three successful transfers on the same club/day; a fourth attempt is rejected with a clear daily-limit message and no state change.

**Acceptance Scenarios**:

1. **Given** a club has already completed three Mentor Transfers today (UTC day), **When** the manager attempts a fourth, **Then** the action is rejected with a clear daily-limit message and balances are unchanged.
2. **Given** the UTC day rolls over, **When** the manager transfers again, **Then** the daily count resets and transfers are allowed up to three again.

---

### Edge Cases

- Source is not at potential ceiling → transfer rejected; allocate skills (if any) remains the normal path.
- Target is already at potential ceiling (or otherwise ineligible to receive mentor XP) → transfer rejected.
- Source and target are not owned by the same club → transfer rejected.
- Source has 1–4 SP → Mentor Transfer unavailable / rejected (minimum 5 SP = 1 mentor unit).
- Daily club transfer limit (3) already reached → rejected with clear copy.
- Target is busy under an active match lock → transfer rejected (same Development match-lock as drills/fusion).
- Source is injured or fatigued → mentoring remains allowed (not a physical activity).
- Target cannot absorb full `500×N` XP (near level cap) → transfer rejected before SP debit; Max amount is capped to headroom.
- Manager sells or transfers the source card after mentoring → youth keeps gained XP; no rollback of past mentor grants.
- Double-tap / concurrent confirm on the same transfer → at most one successful debit/credit; second attempt fails safely.
- Club has many maxed sources → each can contribute SP independently, still bound by the shared daily transfer count of 3.
- Position mismatch (e.g. ST mentor → CM youth) → allowed; mentoring is not position-locked.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Managers MUST be able to initiate Mentor Transfer only from a club-owned source card that has reached its potential ceiling and holds convertible surplus skill points.
- **FR-002**: Conversion MUST use a fixed tax: **5 skill points = 1 mentor unit = 500 experience** on the target (integer mentor units only; leftover SP below 5 stays on the source).
- **FR-003**: Mentor Transfer MUST grant experience to a single same-club non-maxed target card chosen by the manager.
- **FR-004**: Target experience MUST flow through the existing single card-XP progression pipe (same leveling, skill-point unlock, and ceiling behavior as other XP sources).
- **FR-005**: Each successful transfer MUST deduct the exact SP spent from the source and MUST NOT mint SP outside normal level-up / claim rules.
- **FR-006**: Clubs MUST be limited to **3 successful Mentor Transfers per UTC day**.
- **FR-007**: Mentor Transfer daily pacing MUST be independent of the existing per-card skill-allocation daily pacing (allocation caps still govern spending unlocked SP on stats).
- **FR-008**: The Development Allocate Skills flow MUST offer Mentor Transfer for eligible maxed sources and MUST leave non-maxed allocate-stat behavior unchanged.
- **FR-009**: Before commit, the manager MUST see a confirmation preview of SP spent, mentor units, XP granted, and expected target level impact.
- **FR-010**: Player profile for eligible maxed cards MUST surface Mentor Ready conversion status; non-maxed profiles MUST not show mentor chrome.
- **FR-011**: Transfers MUST reject with clear manager-facing reasons for: ineligible source, ineligible target, insufficient SP, daily limit, ownership mismatch, and active match locks.
- **FR-012**: Mentor Transfusion MUST NOT change match simulation, match XP rates, coin economy, energy economy, marketplace pricing formulas, league points, or require a new slash command (extend existing Development / profile surfaces only).
- **FR-013**: Successful transfers MUST be auditable for daily-cap enforcement (append-only transfer history per club/day).
- **FR-014**: Injury/fatigue on the source MUST NOT block mentoring; physical match readiness is unrelated to SP conversion.

### Key Entities

- **Mentor Source Card**: Club-owned player card at potential ceiling holding surplus skill points eligible for conversion.
- **Mentor Target Card**: Club-owned non-maxed player card that may receive mentor experience.
- **Mentor Unit (MP)**: Converted unit from SP (5 SP → 1 MP → 500 XP).
- **Mentor Transfer**: One atomic club action that spends SP from a source and grants XP to a target, counting toward the daily club transfer limit.
- **Mentor Transfer Log**: Append-only record of successful transfers used to enforce the daily limit and support audit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A manager with an eligible maxed source (≥ 5 SP) and eligible target can complete a Mentor Transfer end-to-end in under 2 minutes from the Development hub without leaving Discord.
- **SC-002**: 100% of rejected transfer attempts (ineligible source/target, insufficient SP, daily limit, ownership, busy lock) leave both cards’ SP/XP unchanged and show a clear reason.
- **SC-003**: After three successful transfers in one UTC day, a fourth attempt is blocked for that club until the next UTC day in 100% of trials.
- **SC-004**: Non-maxed Allocate Skills and all match / store / marketplace / league flows behave identically to pre-feature baselines in regression checks (no unintended XP, coin, or energy changes).
- **SC-005**: Managers can identify Mentor Ready status on an eligible maxed card from either Allocate Skills or player profile without consulting external docs.
- **SC-006**: Converting N mentor units always deducts exactly `5×N` skill points and grants exactly `500×N` experience before existing progression ceilings apply (verified on sample transfers of 1, 3, 5, and Max).

## Assumptions

- “Potential ceiling” / “maxed” for mentor eligibility means the card can no longer usefully allocate remaining SP because overall has reached potential (the same ceiling managers hit today when allocate fails), not merely “high level.”
- Cross-position mentoring is allowed (no same-position requirement).
- Minimum convertible chunk is 5 SP; partial mentor units are not granted.
- Daily transfer limit is **per club**, shared across all maxed sources (not 3 per card).
- Mentor XP does not consume the daily **match** XP cap; it is a separate development action analogous to fusion XP in spirit (still through the single XP pipe).
- No coin cost and no energy cost for mentoring in v1.
- No feature flag service is required for v1: safety comes from additive schema + RPC gating + UI only shown when eligible; rollback is “hide UI + stop calling RPC” without destructive data backfill.
- Existing surplus SP on already-maxed cards becomes usable immediately when the feature ships (no retroactive recalculation).
- Selling/trading the source after a transfer does not claw back XP from past targets.
- Target busy locks mirror Development norms (active match lock and in-drill where already enforced elsewhere).
- Competitive brake remains the existing daily **stat allocation** cap on the youth card: mentoring accelerates levels/SP unlock faster than matches alone, but does not raise how many SP can be applied to stats per day during the pacing window.
- Out of scope for v1: marketplace value changes, new slash commands, match-engine changes, store items that buy mentor units, and automatic (AI) mentor suggestions.

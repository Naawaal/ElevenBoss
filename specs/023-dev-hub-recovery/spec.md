# Feature Specification: Development Hub Recovery

**Feature Branch**: `023-dev-hub-recovery`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "Relocate player fatigue recovery out of Training Drills into a dedicated Recover action on the main `/development` hub. Remove Recovery from drills UI completely. Add a Recover button that lets managers multi-select 1–3 eligible players, confirm energy cost, apply fatigue restore, and refresh the hub. Exclude injured and in-hospital players. Keep energy cost configurable (default 5). Ponytail: move only — no new complexity."

## Background & Motivation

Active Recovery Sessions already exist (009 / 010 / US-39): managers restore fatigue for action energy with **0 XP / 0 coins**. Today that action lives **inside Training Drills**, sharing the same player/drill picker as skill drills. Managers confuse fitness rest with skill improvement, and drill copy has to explain both systems at once.

This feature **relocates** the same Recovery Session concept to a first-class **Recover** button on the main Development hub (alongside Training Drills, Evolutions, Allocate Skills, Card Fusion). It does **not** invent a new recovery formula, a new slash command, or Store physio consumables. Passive daily recovery, Hospital injury care, bench rest, and match fatigue drain stay unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover from the Development Hub (Priority: P1)

As a manager, I open `/development` and see a clear **Recover** action next to the other hub buttons. I can send one or more tired players through Recovery without opening Training Drills.

**Why this priority**: Without a dedicated hub entry, Recovery stays buried in drills and the confusion remains. A hub-level Recover path alone is a shippable MVP.

**Independent Test**: From `/development`, tap Recover, select an eligible fatigued player, confirm, and verify fatigue rises by the Recovery amount while XP/coins are unchanged — without ever opening Training Drills.

**Acceptance Scenarios**:

1. **Given** a registered manager opens `/development`, **When** the hub embed loads, **Then** a **Recover** button is visible alongside the existing Development actions (Training Drills, Evolutions, Allocate Skills, Card Fusion).
2. **Given** the manager taps **Recover**, **When** the selection view opens, **Then** they can choose **1 to 3** eligible players and see each player's current fatigue percentage in the selection UI.
3. **Given** at least one eligible player is selected, **When** the manager continues, **Then** a confirmation summary lists who will recover, the fatigue gain per player, and the **total** action-energy cost before any energy is spent.
4. **Given** the manager confirms with enough action energy, **When** Recovery completes, **Then** every selected player's fatigue increases by the published Recovery amount (capped at 100), no XP/coins/stats change, total energy is deducted, and the manager receives a clear success message plus a refreshed Development hub.

---

### User Story 2 - Training Drills Are Skill-Only (Priority: P1)

As a manager using Training Drills, I only see skill-drill choices. Recovery is no longer offered, labeled, or implied inside the drills flow.

**Why this priority**: Leaving a leftover Recovery option in drills defeats the relocation and reintroduces the confusion this feature is meant to fix.

**Independent Test**: Open Training Drills for an eligible fatigued player; confirm Recovery Session is absent from options and copy; confirm skill drills still work.

**Acceptance Scenarios**:

1. **Given** a fatigued eligible player, **When** the manager opens Training Drills, **Then** only skill-drill options appear — there is no Recovery Session choice.
2. **Given** Training Drills hub/copy text, **When** the manager reads it, **Then** it describes skill drills (XP/coins/energy/daily slots) and does **not** advertise Recovery Sessions.
3. **Given** Recovery previously shared drill UI state, **When** this feature ships, **Then** managers cannot trigger Recovery by any remaining drills control or stale drills copy.

---

### User Story 3 - Eligibility and Hospital Boundaries (Priority: P2)

As a manager, I only pick players who can actually benefit from manual Recovery, and I am steered to Hospital when the player is injured or already in Hospital care.

**Why this priority**: Prevents double-dipping with Hospital accelerated recovery and avoids wasted energy on fully rested or unavailable cards.

**Independent Test**: Attempt Recover with injured, in-hospital, fully rested, and eligible tired players; only the last group is selectable / confirmable.

**Acceptance Scenarios**:

1. **Given** a player is injured and/or in Hospital, **When** the manager opens Recover selection, **Then** that player is not selectable for Recovery (or is clearly blocked with Hospital guidance).
2. **Given** a non-injured player at fatigue 100, **When** the manager opens Recover selection, **Then** that player is not selectable (already fully rested).
3. **Given** a non-injured, non-hospital player with fatigue below 100 on the manager's club roster (not retired, not in academy), **When** Recover selection opens, **Then** that player appears with current fatigue % shown.
4. **Given** no eligible players, **When** the manager taps Recover, **Then** they see an empty-state message explaining why nobody can recover right now.

---

### User Story 4 - Affordability and Partial Failure Clarity (Priority: P2)

As a manager, I understand energy cost before I commit, and I get the same class of clear failure messaging used elsewhere on Development when I cannot afford Recovery or a race condition blocks it.

**Why this priority**: Multi-select makes total cost easy to misread; confirmation and failures must stay trustworthy.

**Independent Test**: Try Recover with insufficient energy and with a mid-flow eligibility change; confirm no silent partial success without explanation.

**Acceptance Scenarios**:

1. **Given** selected players whose total Recovery energy cost exceeds available action energy, **When** the manager confirms, **Then** Recovery is rejected, no fatigue changes, and messaging matches existing Development affordability patterns.
2. **Given** the manager double-taps confirm, **When** the second confirm arrives, **Then** at most one successful Recovery batch applies for that selection (no double energy charge / double fatigue grant for the same confirm).
3. **Given** a selected player becomes ineligible between selection and confirm (e.g. admitted to Hospital), **When** confirm runs, **Then** the manager gets a clear failure for that case and is not charged as if the full batch succeeded.

---

### Edge Cases

- Selecting exactly 1 player works the same as selecting 3 (batch size is inclusive).
- Selecting more than 3 is impossible in the UI (hard cap).
- Near-full fatigue (e.g. 90): Recovery still applies and clamps at 100; no overshoot.
- Mix of eligible and ineligible players: ineligible never appear as confirmable targets.
- Zero action energy: Recover button may remain visible, but confirm fails with affordability messaging (or selection warns early if energy is already insufficient for even one player).
- Bot-controlled clubs: no interactive Recover UI required; passive/Hospital paths unchanged.
- Stale hub embed after bot restart: Recover uses the same short-lived hub view timeout pattern as other Development buttons.
- Concurrent Recover + skill drill on the same card: Recovery does not grant XP; skill drills remain independent. If both are attempted in the same moment, each path still respects its own gates and energy balance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a **Recover** action on the main `/development` hub embed/view (no new slash command).
- **FR-002**: System MUST remove Recovery Session as a choice, label, and explanatory line from the Training Drills flow so drills are skill-only.
- **FR-003**: Recover MUST let the manager select **between 1 and 3** eligible players in one session before confirmation.
- **FR-004**: Eligible players MUST be owned club roster cards that are **not** retired, **not** in academy, **not** injured, **not** in Hospital, and have fatigue **strictly below 100**.
- **FR-005**: Selection UI MUST show each eligible player's **current fatigue percentage** next to their identity.
- **FR-006**: Before spending energy, system MUST show a confirmation summary listing selected players, per-player fatigue gain, and **total** action-energy cost.
- **FR-007**: On successful confirm, system MUST apply the published Recovery fatigue grant to **each** selected player (default **+40**, clamped to 100) and MUST NOT grant XP, skill points, coins, or direct stat increases.
- **FR-008**: Action-energy cost MUST be configurable via existing game configuration (default **5** energy **per selected player**); total cost for N players is **N × per-player energy**.
- **FR-009**: Successful Recover MUST deduct exactly the confirmed total energy and MUST refuse the whole batch when the club cannot afford that total.
- **FR-010**: After success, system MUST refresh/return the manager to an updated Development hub state and send a confirmation message naming who recovered and what was spent/gained.
- **FR-011**: Recovery MUST remain **instant** (one confirm → result); no multi-hour queued job.
- **FR-012**: Recovery MUST **not** consume Training Drills daily capacity (per-card or per-club skill-drill slots). Recover is energy-gated only.
- **FR-013**: Hospital injury care, daily passive fatigue recovery, bench rest, match drain, and fatigue penalty tiers MUST remain unchanged by this relocation.
- **FR-014**: Managers MUST receive clear success and failure feedback for empty eligibility, injury/Hospital blocks, already-rested blocks, insufficient energy, and mid-flow eligibility loss.
- **FR-015**: Physio / Store instant-full-fatigue consumables remain **out of scope**.

### Key Entities

- **Development Hub**: Existing `/development` surface; gains a Recover entry point; Training Drills lose Recovery.
- **Recovery Session (batch)**: Instant fitness restore for 1–3 eligible players; 0 XP / 0 coins; configurable energy per player; no skill-drill slot consumption.
- **Player Card Fatigue**: Existing 0–100 fitness value; restored by Recover, passive daily recovery, and bench rest; drained by competitive starts.
- **Hospital Care**: Existing injury path; mutually exclusive with Recover eligibility while injured or in Hospital.
- **Action Energy**: Existing club energy pool; sole pacing gate for Recover after relocation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Managers can complete a successful Recover for 1 eligible player from the Development hub in under 1 minute without opening Training Drills.
- **SC-002**: 100% of Training Drills entry paths show zero Recovery Session options or Recovery advertising copy after ship.
- **SC-003**: In usability checks, managers correctly identify Recover as fitness-only (0 XP) and Training Drills as skill progression on first attempt at least 90% of the time.
- **SC-004**: Confirming a 3-player Recover charges exactly 3× the configured per-player energy and restores fatigue for all three when affordable; insufficient energy restores **zero** of the three.
- **SC-005**: Injured and in-Hospital players never receive a successful Recover grant in acceptance testing (0 false successes).
- **SC-006**: Support/confusion reports about “Recovery hidden inside drills” drop after release relative to the pre-change baseline (tracked qualitatively in the first two weeks).

## Assumptions

- Default Recovery fatigue grant remains **+40** (existing published amount); this feature relocates UX, it does not retune the grant unless ops already changed config.
- Default energy cost remains **5 per player** (existing `fatigue_recovery_energy` intent from 010); batch total scales linearly with selection size.
- “Squad” for selection means the manager’s **club roster** excluding academy and retired cards — not strictly the current matchday XI — so reserves can recover too.
- Detaching Recover from skill-drill daily slots is intentional: Recovery is no longer a “drill,” only an energy spend. Passive daily recovery and Hospital paths are untouched.
- Existing Development hub patterns (defer immediately, ephemeral hub edits, short-lived views, owner checks) apply to Recover without inventing a new interaction style.
- Bot clubs do not need the interactive Recover button for league correctness.
- No new player-facing slash command; Recover is hub-button only.
- Rollback means restoring Recover inside Training Drills and removing the hub Recover button — behavior returns to the pre-relocation UX without changing Hospital/passive formulas.

## Out of Scope

- New slash commands or Store physio SKUs
- Changing match fatigue drain, bench rest amounts, or Hospital curves
- Changing Training Ground passive daily recovery math
- Recovering more than 3 players in one confirm
- Auto-recover / scheduled Recover jobs
- Mentoring, fusion, evolutions, or skill-allocation UX changes beyond coexistence on the same hub
